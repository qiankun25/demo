import base64
import hashlib
import json
import mimetypes
import os
import re
import shutil
import sys
import time
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

import httpx
from fastapi import FastAPI, HTTPException, status, UploadFile, File, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, model_validator
from redis.asyncio import Redis
from sqlalchemy import Column, DateTime, MetaData, String, Table, Text, func, insert, literal_column, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

SERVICE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SERVICE_DIR, "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
if SERVICE_DIR not in sys.path:
    sys.path.insert(0, SERVICE_DIR)

from nexus_tool import config
from tool_services.translator_service import prompt_config
from unified_backend.router import router as unified_router
from unified_backend.core.image_translate import translate_image_bytes as baidu_translate_image_bytes
from unified_backend.core.pipeline import translate_pdf_to_markdown
from unified_backend.config import settings as unified_settings

app = FastAPI(
    title="Translator Service",
    version="0.1.0",
    description="多模态翻译服务（支持文本和图片）",
)

# 挂载新版 unified_backend 的增强接口（保持端口不变）
app.include_router(unified_router)

metadata = MetaData()
glossary_table = Table(
    "translator_glossary",
    metadata,
    Column("term", String(128), primary_key=True),
    Column("definition", Text, nullable=False),
    Column("domain", String(64), nullable=False, server_default="research"),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column("updated_at", DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False),
)

glossary_engine = (
    create_async_engine(config.TRANSLATOR_DB_URL, future=True)
    if config.TRANSLATOR_DB_URL
    else None
)
glossary_sessionmaker = (
    async_sessionmaker(glossary_engine, expire_on_commit=False)
    if glossary_engine
    else None
)

redis_client: Optional[Redis] = None
if config.TRANSLATOR_REDIS_URL:
    redis_client = Redis.from_url(config.TRANSLATOR_REDIS_URL, decode_responses=True)

CACHE_KEY_PREFIX = "translator:cache:"

class TranslateRequest(BaseModel):
    text: str = Field("", description="原文内容")
    images: List[str] = Field(default_factory=list, description="图片列表（本地路径或 URL）")
    target_lang: str = Field("zh", description="目标语言（如 zh/en/ja）")

class ImageTranslation(BaseModel):
    input: str
    caption: str
    extracted_text: str
    translated_text: str

class TranslateResponse(BaseModel):
    text_translated: str
    images_translated: List[ImageTranslation]
    meta: Dict[str, Any]


class GlossaryTermResponse(BaseModel):
    term: str
    definition: str
    domain: str
    created_at: datetime
    updated_at: datetime


class GlossaryCreateRequest(BaseModel):
    term: str = Field(..., min_length=1, description="术语名称（唯一）")
    definition: str = Field(..., min_length=1, description="术语对应的解释或指定翻译")
    domain: str = Field("research", description="所属领域/语料（默认 research）")


class GlossaryUpdateRequest(BaseModel):
    definition: Optional[str]
    domain: Optional[str]

    @model_validator(mode="before")
    @classmethod
    def _require_at_least_one(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        if not values.get("definition") and not values.get("domain"):
            raise ValueError("提供 definition 或 domain 至少其一")
        return values


def _glossary_row_to_payload(row: Any) -> Dict[str, Any]:
    mapping = row._mapping if hasattr(row, "_mapping") else row
    return {
        "term": mapping["term"],
        "definition": mapping["definition"],
        "domain": mapping.get("domain") or "research",
        "created_at": mapping["created_at"],
        "updated_at": mapping["updated_at"],
    }


def _translation_cache_key(req: TranslateRequest) -> str:
    normalized = {
        "text": (req.text or "").strip(),
        "images": req.images or [],
        "target_lang": (req.target_lang or "").strip().lower(),
    }
    canonical = json.dumps(normalized, sort_keys=True, ensure_ascii=False)
    key_hash = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"{CACHE_KEY_PREFIX}{key_hash}"


async def _get_cached_translation(cache_key: str) -> Optional[TranslateResponse]:
    if not redis_client:
        return None
    try:
        payload = await redis_client.get(cache_key)
    except Exception:
        return None
    if not payload:
        return None
    try:
        data = json.loads(payload)
        return TranslateResponse.model_validate(data)
    except Exception:
        try:
            await redis_client.delete(cache_key)
        except Exception:
            pass
        return None


async def _set_cached_translation(cache_key: str, resp: TranslateResponse) -> None:
    if not redis_client or not cache_key or config.TRANSLATOR_CACHE_TTL_SECONDS <= 0:
        return
    try:
        await redis_client.set(
            cache_key,
            resp.model_dump_json(),
            ex=config.TRANSLATOR_CACHE_TTL_SECONDS,
        )
    except Exception:
        pass


class PromptUpdateRequest(BaseModel):
    template: str = Field(..., min_length=1, description="Template for the system prompt")
    description: Optional[str] = Field(None, description="Optional explanation of the prompt's intent")


class TranslatePaperResponse(BaseModel):
    text_translated: str = Field(..., description="提取并翻译后的完整论文文本")
    meta: Dict[str, Any] = Field(..., description="元数据信息")

def _to_image_part(image_ref: str) -> Dict[str, Any]:
    ref = (image_ref or "").strip()
    if not ref:
        raise ValueError("empty image ref")

    if ref.startswith("http://") or ref.startswith("https://"):
        return {"type": "image_url", "image_url": {"url": ref}}

    # file path
    if not os.path.exists(ref):
        raise FileNotFoundError(f"image file not found: {ref}")

    mime, _ = mimetypes.guess_type(ref)
    if not mime:
        mime = "application/octet-stream"
    with open(ref, "rb") as f:
        b = f.read()
    b64 = base64.b64encode(b).decode("utf-8")
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}

async def _load_image_bytes(image_ref: str) -> bytes:
    ref = (image_ref or "").strip()
    if not ref:
        raise ValueError("empty image ref")
    if ref.startswith("http://") or ref.startswith("https://"):
        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            r = await client.get(ref)
            r.raise_for_status()
            return r.content
    if not os.path.exists(ref):
        raise FileNotFoundError(f"image file not found: {ref}")
    with open(ref, "rb") as f:
        return f.read()

def _extract_baidu_ocr_blocks(res: Dict[str, Any]) -> List[Tuple[str, str]]:
    """
    尽量兼容百度图片翻译 API 的不同返回结构，抽取 (src, dst) 列表。
    """
    if not isinstance(res, dict):
        return []

    # 常见结构：{"data":{"content":[{"src":"...","dst":"..."}]}}
    data = res.get("data") if isinstance(res.get("data"), dict) else None
    if data and isinstance(data.get("content"), list):
        out: List[Tuple[str, str]] = []
        for item in data["content"]:
            if not isinstance(item, dict):
                continue
            src = (item.get("src") or item.get("src_text") or "").strip()
            dst = (item.get("dst") or item.get("dst_text") or "").strip()
            if src or dst:
                out.append((src, dst))
        return out

    # 兼容：{"result":{"blocks":[{"src_text":...,"dst_text":...}]}}
    result = res.get("result") if isinstance(res.get("result"), dict) else None
    if result and isinstance(result.get("blocks"), list):
        out2: List[Tuple[str, str]] = []
        for b in result["blocks"]:
            if not isinstance(b, dict):
                continue
            src = (b.get("src") or b.get("src_text") or "").strip()
            dst = (b.get("dst") or b.get("dst_text") or "").strip()
            if src or dst:
                out2.append((src, dst))
        return out2

    return []

async def _caption_image_siliconflow(image_ref: str, target_lang: str) -> str:
    """
    用 SiliconFlow 多模态模型仅生成图片 caption（不做 OCR 翻译）。
    """
    if not config.SILICONFLOW_API_KEY:
        return ""

    system_prompt = prompt_config.render_prompt("image_caption", target_lang=target_lang)

    headers = {
        "Authorization": f"Bearer {config.SILICONFLOW_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": config.DEFAULT_MODEL,
        "messages": [
            {
                "role": "system",
                "content": system_prompt,
            },
            {"role": "user", "content": [{"type": "text", "text": "Describe this image."}, _to_image_part(image_ref)]},
        ],
        "max_tokens": 200,
        "temperature": 0.2,
        "top_p": 0.9,
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(config.API_BASE, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
    choices = data.get("choices") or []
    if choices and isinstance(choices[0], dict):
        msg = choices[0].get("message") or {}
        if isinstance(msg, dict):
            return (msg.get("content") or "").strip()
    return ""

async def _translate_multimodal(text: str, images: List[str], target_lang: str) -> Dict[str, Any]:
    system_prompt = prompt_config.render_prompt("multimodal_translation", target_lang=target_lang)

    user_parts: List[Dict[str, Any]] = []
    if text:
        user_parts.append({"type": "text", "text": f"Text to translate:\n{text}"})
    else:
        user_parts.append({"type": "text", "text": "No text provided. Only process images."})

    for img in images or []:
        # For the model, we provide the reference and the content
        user_parts.append({"type": "text", "text": f"Image input: {img}"})
        try:
            user_parts.append(_to_image_part(img))
        except Exception as e:
            # If image processing fails, we skip this image part but keep the text ref
            user_parts.append({"type": "text", "text": f"(Image processing failed: {str(e)})"})

    headers = {
        "Authorization": f"Bearer {config.SILICONFLOW_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": config.DEFAULT_MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_parts},
        ],
        "max_tokens": config.TRANSLATE_MAX_TOKENS,
        "temperature": config.TRANSLATE_TEMPERATURE,
        "top_p": config.TRANSLATE_TOP_P,
    }

    async with httpx.AsyncClient(timeout=90.0) as client:
        resp = await client.post(config.API_BASE, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()

    choices = data.get("choices") or []
    content = ""
    if choices and isinstance(choices[0], dict):
        msg = choices[0].get("message") or {}
        if isinstance(msg, dict):
            content = (msg.get("content") or "").strip()

    if not content:
        raise RuntimeError("empty model response")

    # Parse JSON (model might wrap it in ```json)
    cleaned = content
    if cleaned.startswith("```"):
        cleaned = cleaned.strip().strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()

    try:
        out = json.loads(cleaned)
        if not isinstance(out, dict):
            raise ValueError("model output is not a dict")
        out.setdefault("text_translated", "")
        out.setdefault("images_translated", [])
        
        if isinstance(out.get("images_translated"), list):
            fixed = []
            for i, item in enumerate(out["images_translated"]):
                if not isinstance(item, dict):
                    continue
                item.setdefault("input", images[i] if i < len(images) else "")
                item.setdefault("caption", "")
                item.setdefault("extracted_text", "")
                item.setdefault("translated_text", "")
                fixed.append(item)
            out["images_translated"] = fixed
        return out
    except Exception:
        # Fallback if JSON parsing fails
        return {
            "text_translated": content,
            "images_translated": [],
        }

@app.get("/health")
async def health():
    ready = await health_ready()
    code = ready.status_code
    payload = ready.body
    try:
        shaped = json.loads(payload.decode("utf-8"))
    except Exception:
        shaped = {"status": "unknown", "raw": str(payload)}
    shaped.setdefault("service", "translator_service")
    shaped.setdefault("timestamp", time.time())
    return JSONResponse(status_code=code, content=shaped)


@app.get("/health/live")
async def health_live():
    return {"status": "alive"}


@app.get("/health/ready")
async def health_ready():
    components: Dict[str, Any] = {}
    ok = True

    # External credentials presence checks (no network calls in readiness)
    has_siliconflow = bool((config.SILICONFLOW_API_KEY or "").strip())
    components["siliconflow_api_key"] = "configured" if has_siliconflow else "missing"

    has_baidu = bool(os.getenv("BAIDU_APP_ID", "").strip()) and bool(os.getenv("BAIDU_SECRET_KEY", "").strip())
    components["baidu_ocr_creds"] = "configured" if has_baidu else "missing"

    # This service can still operate if at least one backend is available:
    # - Text translation requires SiliconFlow
    # - Image translation prefers Baidu, but can fallback to SiliconFlow multimodal if configured
    if not (has_siliconflow or has_baidu):
        ok = False

    if redis_client:
        try:
            await redis_client.ping()
            components["redis_cache"] = "healthy"
        except Exception:
            components["redis_cache"] = "unhealthy"
            ok = False
    else:
        components["redis_cache"] = "disabled"

    if glossary_engine:
        try:
            async with glossary_engine.connect() as conn:
                await conn.execute(select(literal_column("1")))
            components["glossary_db"] = "healthy"
        except Exception:
            components["glossary_db"] = "unhealthy"
            ok = False
    else:
        components["glossary_db"] = "disabled"

    status_code = status.HTTP_200_OK if ok else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(status_code=status_code, content={"status": "ready" if ok else "not ready", "components": components})


@app.on_event("startup")
async def _ensure_glossary_tables():
    if glossary_engine:
        async with glossary_engine.begin() as conn:
            await conn.run_sync(metadata.create_all)


@app.on_event("shutdown")
async def _cleanup_resources():
    if redis_client:
        await redis_client.close()
    if glossary_engine:
        await glossary_engine.dispose()


def _format_prompt_entry(key: str, entry: Dict[str, str]) -> Dict[str, str]:
    return {
        "key": key,
        "template": entry.get("template", ""),
        "description": entry.get("description", "") or "",
    }


@app.get("/prompts")
async def list_prompts():
    return {"prompts": [_format_prompt_entry(k, v) for k, v in prompt_config.list_prompts().items()]}


@app.get("/prompts/{prompt_key}")
async def get_prompt(prompt_key: str):
    entry = prompt_config.get_prompt_entry(prompt_key)
    if not entry:
        raise HTTPException(status_code=404, detail="prompt not found")
    return _format_prompt_entry(prompt_key, entry)


@app.put("/prompts/{prompt_key}")
async def update_prompt(prompt_key: str, req: PromptUpdateRequest):
    try:
        updated = prompt_config.update_prompt(prompt_key, template=req.template, description=req.description)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _format_prompt_entry(prompt_key, updated)


@app.post("/translate", response_model=TranslateResponse)
async def translate(req: TranslateRequest):
    cache_key = _translation_cache_key(req)
    cached = await _get_cached_translation(cache_key)
    if cached:
        return cached

    try:
        # 1) 文本翻译（沿用旧 SiliconFlow 模型；如果没提供文本则跳过）
        text_translated = ""
        model_used = None
        if (req.text or "").strip():
            if not config.SILICONFLOW_API_KEY:
                raise HTTPException(status_code=500, detail="SILICONFLOW_API_KEY not configured")
            result_text = await _translate_multimodal(text=req.text, images=[], target_lang=req.target_lang)
            text_translated = result_text.get("text_translated", "")
            model_used = config.DEFAULT_MODEL

        # 2) 图片翻译（优先走新版百度 OCR 翻译；失败则回退旧 multimodal 一把梭）
        images_out: List[Dict[str, Any]] = []
        for img in req.images or []:
            img_ref = (img or "").strip()
            if not img_ref:
                continue

            caption = ""
            extracted_text = ""
            translated_text = ""

            try:
                img_bytes = await _load_image_bytes(img_ref)
                baidu_res = baidu_translate_image_bytes(img_bytes)
                blocks = _extract_baidu_ocr_blocks(baidu_res)
                extracted_text = "\n".join([s for s, _ in blocks if s]).strip()
                translated_text = "\n".join([t for _, t in blocks if t]).strip()
                if config.SILICONFLOW_API_KEY:
                    caption = await _caption_image_siliconflow(img_ref, req.target_lang)
                model_used = model_used or ("baidu+%s" % config.DEFAULT_MODEL if config.SILICONFLOW_API_KEY else "baidu")
            except Exception:
                # fallback：旧多模态翻译（包含 caption/OCR/翻译）
                if not config.SILICONFLOW_API_KEY:
                    raise HTTPException(status_code=500, detail="Image translation failed and SILICONFLOW_API_KEY not configured for fallback")
                fallback = await _translate_multimodal(text="", images=[img_ref], target_lang=req.target_lang)
                one = (fallback.get("images_translated") or [{}])[0] if isinstance(fallback.get("images_translated"), list) else {}
                caption = (one.get("caption") or "").strip()
                extracted_text = (one.get("extracted_text") or "").strip()
                translated_text = (one.get("translated_text") or "").strip()
                model_used = model_used or config.DEFAULT_MODEL

            images_out.append(
                {
                    "input": img_ref,
                    "caption": caption,
                    "extracted_text": extracted_text,
                    "translated_text": translated_text,
                }
            )
        
        meta = {
            "target_lang": req.target_lang,
            "image_count": len(req.images or []),
            "model": model_used or (config.DEFAULT_MODEL if config.SILICONFLOW_API_KEY else "baidu")
        }
        
        response = TranslateResponse(
            text_translated=text_translated,
            images_translated=images_out,
            meta=meta
        )
        await _set_cached_translation(cache_key, response)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _assert_glossary_enabled():
    if not glossary_sessionmaker:
        raise HTTPException(status_code=503, detail="Glossary database not configured")


@app.get("/glossary")
async def list_glossary(domain: Optional[str] = None):
    _assert_glossary_enabled()
    async with glossary_sessionmaker() as session:
        stmt = select(glossary_table)
        if domain:
            stmt = stmt.where(glossary_table.c.domain == domain)
        stmt = stmt.order_by(glossary_table.c.term)
        result = await session.execute(stmt)
        terms = [
            GlossaryTermResponse.model_validate(_glossary_row_to_payload(row)).model_dump()
            for row in result.fetchall()
        ]
    return {"terms": terms}


@app.get("/glossary/{term}", response_model=GlossaryTermResponse)
async def get_glossary_term(term: str):
    _assert_glossary_enabled()
    normalized_term = (term or "").strip()
    if not normalized_term:
        raise HTTPException(status_code=400, detail="term required")
    async with glossary_sessionmaker() as session:
        result = await session.execute(
            select(glossary_table).where(glossary_table.c.term == normalized_term)
        )
        row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"term {normalized_term} not found")
    return GlossaryTermResponse.model_validate(_glossary_row_to_payload(row))


@app.post("/glossary", response_model=GlossaryTermResponse, status_code=201)
async def create_glossary(req: GlossaryCreateRequest):
    _assert_glossary_enabled()
    term_value = req.term.strip()
    if not term_value:
        raise HTTPException(status_code=400, detail="term required")
    definition_value = req.definition.strip()
    if not definition_value:
        raise HTTPException(status_code=400, detail="definition required")
    domain_value = (req.domain or "research").strip() or "research"

    async with glossary_sessionmaker() as session:
        stmt = (
            insert(glossary_table)
            .values(term=term_value, definition=definition_value, domain=domain_value)
            .returning(*glossary_table.c)
        )
        try:
            result = await session.execute(stmt)
            await session.commit()
        except IntegrityError:
            await session.rollback()
            raise HTTPException(status_code=409, detail=f"Glossary term {term_value} already exists")
        row = result.fetchone()
    if not row:
        raise HTTPException(status_code=500, detail="failed to persist glossary entry")
    return GlossaryTermResponse.model_validate(_glossary_row_to_payload(row))


@app.put("/glossary/{term}", response_model=GlossaryTermResponse)
async def update_glossary(term: str, req: GlossaryUpdateRequest):
    _assert_glossary_enabled()
    normalized_term = (term or "").strip()
    if not normalized_term:
        raise HTTPException(status_code=400, detail="term required")
    updated_values: Dict[str, Any] = {}
    if req.definition is not None:
        definition_value = req.definition.strip()
        if not definition_value:
            raise HTTPException(status_code=400, detail="definition cannot be empty")
        updated_values["definition"] = definition_value
    if req.domain is not None:
        updated_values["domain"] = req.domain.strip() or "research"
    if not updated_values:
        raise HTTPException(status_code=400, detail="no changes provided")

    stmt = (
        update(glossary_table)
        .where(glossary_table.c.term == normalized_term)
        .values(**updated_values, updated_at=func.now())
        .returning(*glossary_table.c)
    )
    async with glossary_sessionmaker() as session:
        result = await session.execute(stmt)
        await session.commit()
        row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail=f"term {normalized_term} not found")
    return GlossaryTermResponse.model_validate(_glossary_row_to_payload(row))


@app.post("/translate-paper", response_model=TranslatePaperResponse)
async def translate_paper(
    file: UploadFile = File(...),
    target_lang: str = Form("zh")
):
    """
    论文翻译接口 - 符合 API_REFERENCE.md 中的接口声明
    
    上传 PDF 文件并返回翻译后的文本
    """
    # 验证文件类型
    if not file.filename or not file.filename.lower().endswith('.pdf'):
        return JSONResponse(
            status_code=400,
            content={"error": "only PDF files are supported"}
        )
    
    # 确保临时目录存在
    os.makedirs(unified_settings.TMP_DIR, exist_ok=True)
    
    pdf_path = None
    try:
        # 保存上传的 PDF 文件
        pdf_id = str(uuid.uuid4())
        pdf_path = os.path.join(unified_settings.TMP_DIR, f"{pdf_id}.pdf")
        with open(pdf_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
        
        # 执行 PDF 翻译（默认源语言为英文）
        # 注意：translate_pdf_to_markdown 返回的是 markdown 格式，我们需要提取纯文本
        markdown_result = translate_pdf_to_markdown(
            pdf_path,
            source_lang="en",  # 默认源语言为英文
            target_lang=target_lang
        )
        
        # 将 markdown 转换为纯文本（移除 markdown 格式标记）
        # 简单处理：移除图片引用和公式标记，保留文本内容
        # 移除图片引用 ![Image...](...)
        text_translated = re.sub(r'!\[.*?\]\(.*?\)', '', markdown_result)
        # 移除 LaTeX 公式标记 $$...$$ 和 $...$
        text_translated = re.sub(r'\$\$.*?\$\$', '', text_translated, flags=re.DOTALL)
        text_translated = re.sub(r'\$.*?\$', '', text_translated)
        # 清理多余空白
        text_translated = re.sub(r'\n\s*\n', '\n\n', text_translated).strip()
        
        # 如果处理后为空，使用原始 markdown
        if not text_translated:
            text_translated = markdown_result
        
        # 获取模型标识
        model_used = config.DEFAULT_MODEL or unified_settings.SILICONFLOW_MODEL or "deepseek-ai/DeepSeek-V3"
        
        # 提取文件名（不含路径）
        file_name = file.filename or "paper.pdf"
        if '/' in file_name:
            file_name = os.path.basename(file_name)
        
        return TranslatePaperResponse(
            text_translated=text_translated,
            meta={
                "target_lang": target_lang,
                "file_name": file_name,
                "model": model_used
            }
        )
        
    except Exception as e:
        error_msg = str(e)
        # 检查是否是 PDF 解析错误
        if "PDF parsing failed" in error_msg or "parse" in error_msg.lower():
            return JSONResponse(
                status_code=500,
                content={"error": f"PDF parsing failed: {error_msg}"}
            )
        return JSONResponse(
            status_code=500,
            content={"error": f"Translation failed: {error_msg}"}
        )
    finally:
        # 清理临时文件
        if pdf_path and os.path.exists(pdf_path):
            try:
                os.remove(pdf_path)
            except Exception:
                pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)

