import os
import shutil
import uuid
import logging
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import Field

from .config import settings
from .schemas.unified import (
    TranslateRequest, TranslateResponse,
    ImageTranslateResponse,
    TermRequest, TermResponse,
    PDFTranslateResponse
)
from .core.text_translate import translate_text
from .core.image_translate import translate_image_bytes
from .core.term_service_logic import extract_and_calibrate_terms
from .core.pipeline import translate_pdf_to_markdown

# 配置日志
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.TITLE,
    description=settings.DESCRIPTION,
    version=settings.VERSION
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
    allow_methods=settings.CORS_ALLOW_METHODS,
    allow_headers=settings.CORS_ALLOW_HEADERS,
)

# 确保目录存在
os.makedirs(settings.TMP_DIR, exist_ok=True)
os.makedirs(settings.IMAGE_TMP_DIR, exist_ok=True)

@app.get("/")
async def root():
    return {"service": settings.APP_NAME, "status": "running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

# --- 1. 文本翻译接口 ---
@app.post("/api/v1/translate/text", response_model=TranslateResponse, tags=["Translation"])
async def translate_text_api(req: TranslateRequest):
    try:
        result = translate_text(
            text=req.text,
            source_lang=req.source_lang,
            target_lang=req.target_lang
        )
        return TranslateResponse(translated_text=result)
    except Exception as e:
        logger.error(f"文本翻译失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# --- 2. 图片翻译接口 ---
@app.post("/api/v1/translate/image", response_model=ImageTranslateResponse, tags=["Translation"])
async def translate_image_api(file: UploadFile = File(...)):
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="图片内容为空")

    result = translate_image_bytes(content)
    if result.get("error_code") != "0" and result.get("error_code") != 0:
        error_msg = result.get("error_msg", "未知错误")
        logger.error(f"百度图片翻译错误: {error_msg}")
        raise HTTPException(status_code=500, detail=f"翻译失败: {error_msg}")

    return {
        "status": "success",
        "service": "image-translation",
        "result": result.get("result", {})
    }

# --- 3. 术语提取与校准接口 ---
@app.post("/api/v1/terms/extract", response_model=TermResponse, tags=["Terms"])
async def extract_terms_api(req: TermRequest):
    try:
        terms = extract_and_calibrate_terms(req.text)
        return {"terms": terms}
    except Exception as e:
        logger.error(f"术语提取失败: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# --- 4. PDF 翻译接口 ---
@app.post("/api/v1/translate/pdf", response_model=PDFTranslateResponse, tags=["Translation"])
async def translate_pdf_api(
    file: UploadFile = File(...),
    source_lang: str = Form("en"),
    target_lang: str = Form("zh")
):
    pdf_path = None
    try:
        # 保存 PDF
        pdf_id = str(uuid.uuid4())
        pdf_path = os.path.join(settings.TMP_DIR, f"{pdf_id}.pdf")
        with open(pdf_path, "wb") as f:
            shutil.copyfileobj(file.file, f)

        # 执行翻译
        markdown_result = translate_pdf_to_markdown(
            pdf_path,
            source_lang,
            target_lang
        )
        
        return PDFTranslateResponse(
            success=True,
            markdown=markdown_result
        )
        
    except Exception as e:
        logger.error(f"PDF 翻译失败: {str(e)}", exc_info=True)
        return PDFTranslateResponse(
            success=False,
            error=str(e)
        )
    finally:
        if pdf_path and os.path.exists(pdf_path):
            try:
                os.remove(pdf_path)
            except:
                pass

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.HOST, port=settings.PORT)

