import os
import sys
import json
import base64
import mimetypes
from typing import List, Dict, Any, Optional

import httpx
from fastapi import FastAPI, HTTPException, Body
from pydantic import BaseModel, Field

# Ensure we can import from the current directory
sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from nexus_tool import config

app = FastAPI(
    title="Translator Service",
    version="0.1.0",
    description="多模态翻译服务（支持文本和图片）",
)

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
    return {"status": "ok"}

@app.post("/translate", response_model=TranslateResponse)
async def translate(req: TranslateRequest):
    if not config.SILICONFLOW_API_KEY:
        raise HTTPException(status_code=500, detail="SILICONFLOW_API_KEY not configured")
    
    try:
        result = await _translate_multimodal(
            text=req.text, 
            images=req.images, 
            target_lang=req.target_lang
        )
        
        meta = {
            "target_lang": req.target_lang,
            "image_count": len(req.images),
            "model": config.DEFAULT_MODEL
        }
        
        return TranslateResponse(
            text_translated=result.get("text_translated", ""),
            images_translated=result.get("images_translated", []),
            meta=meta
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)

