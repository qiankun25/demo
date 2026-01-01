import os
import sys
import json
import base64
import mimetypes
import time
from typing import List, Dict, Any, Optional, Tuple

import httpx
from fastapi import FastAPI, HTTPException, Body, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

# Ensure we can import from the current directory
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from nexus_tool import config
from unified_backend.router import router as unified_router
from unified_backend.core.image_translate import translate_image_bytes as baidu_translate_image_bytes

app = FastAPI(
    title="Translator Service",
    version="0.1.0",
    description="多模态翻译服务（支持文本和图片）",
)

# 挂载新版 unified_backend 的增强接口（保持端口不变）
app.include_router(unified_router)

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

    headers = {
        "Authorization": f"Bearer {config.SILICONFLOW_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": config.DEFAULT_MODEL,
        "messages": [
            {
                "role": "system",
                "content": f"You are a helpful assistant. Describe the image in {target_lang}. Return a short caption only.",
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
    system_prompt = (
        "You are a professional multilingual translator.\n"
        "You will be given text and optionally images.\n"
        "Task:\n"
        f"1) Translate the given text into {target_lang}.\n"
        f"2) For each image, produce a caption in {target_lang}. If there is readable text, extract it and translate it into {target_lang}.\n"
        "Return STRICT JSON with this schema:\n"
        '{"text_translated": string, "images_translated": [{"input": string, "caption": string, "extracted_text": string, "translated_text": string}]}'
    )

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

    status_code = status.HTTP_200_OK if ok else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(status_code=status_code, content={"status": "ready" if ok else "not ready", "components": components})

@app.post("/translate", response_model=TranslateResponse)
async def translate(req: TranslateRequest):
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
            "image_count": len(req.images),
            "model": model_used or (config.DEFAULT_MODEL if config.SILICONFLOW_API_KEY else "baidu")
        }
        
        return TranslateResponse(
            text_translated=text_translated,
            images_translated=images_out,
            meta=meta
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)

