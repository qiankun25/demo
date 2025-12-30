import os
import shutil
import uuid
import logging

from fastapi import APIRouter, UploadFile, File, Form, HTTPException

from .config import settings
from .schemas.unified import (
    TranslateRequest,
    TranslateResponse,
    ImageTranslateResponse,
    TermRequest,
    TermResponse,
    PDFTranslateResponse,
)
from .core.text_translate import translate_text
from .core.image_translate import translate_image_bytes
from .core.term_service_logic import extract_and_calibrate_terms
from .core.pipeline import translate_pdf_to_markdown

logger = logging.getLogger(__name__)

router = APIRouter()


def _ensure_tmp_dirs() -> None:
    os.makedirs(settings.TMP_DIR, exist_ok=True)
    os.makedirs(settings.IMAGE_TMP_DIR, exist_ok=True)


@router.post("/api/v1/translate/text", response_model=TranslateResponse, tags=["Translation"])
async def translate_text_api(req: TranslateRequest):
    try:
        result = translate_text(text=req.text, source_lang=req.source_lang, target_lang=req.target_lang)
        return TranslateResponse(translated_text=result)
    except Exception as e:
        logger.exception("文本翻译失败")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/v1/translate/image", response_model=ImageTranslateResponse, tags=["Translation"])
async def translate_image_api(file: UploadFile = File(...)):
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="图片内容为空")

    result = translate_image_bytes(content)
    if result.get("error_code") not in (0, "0", None):
        error_msg = result.get("error_msg", "未知错误")
        logger.error("百度图片翻译错误: %s", error_msg)
        raise HTTPException(status_code=500, detail=f"翻译失败: {error_msg}")

    return {
        "status": "success",
        "service": "image-translation",
        "result": result.get("result") or result.get("data") or result,
    }


@router.post("/api/v1/terms/extract", response_model=TermResponse, tags=["Terms"])
async def extract_terms_api(req: TermRequest):
    try:
        terms = extract_and_calibrate_terms(req.text)
        return {"terms": terms}
    except Exception as e:
        logger.exception("术语提取失败")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/v1/translate/pdf", response_model=PDFTranslateResponse, tags=["Translation"])
async def translate_pdf_api(
    file: UploadFile = File(...),
    source_lang: str = Form("en"),
    target_lang: str = Form("zh"),
):
    _ensure_tmp_dirs()

    pdf_path = None
    try:
        pdf_id = str(uuid.uuid4())
        pdf_path = os.path.join(settings.TMP_DIR, f"{pdf_id}.pdf")
        with open(pdf_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        markdown_result = translate_pdf_to_markdown(pdf_path, source_lang, target_lang)
        return PDFTranslateResponse(success=True, markdown=markdown_result)
    except Exception as e:
        logger.exception("PDF 翻译失败")
        return PDFTranslateResponse(success=False, error=str(e))
    finally:
        if pdf_path and os.path.exists(pdf_path):
            try:
                os.remove(pdf_path)
            except Exception:
                pass


