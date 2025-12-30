from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any

# --- Text Translation Schemas ---
class TranslateRequest(BaseModel):
    text: str = Field(..., description="待翻译文本")
    source_lang: str = Field("en", description="源语言")
    target_lang: str = Field("zh", description="目标语言")

class TranslateResponse(BaseModel):
    translated_text: str = Field(..., description="翻译后的文本")

# --- Image Translation Schemas ---
class ImageBlock(BaseModel):
    src_text: str = Field(..., description="图片中识别出的原文")
    dst_text: str = Field(..., description="翻译后的文本")
    confidence: Optional[float] = Field(None, description="识别置信度")

class ImageTranslateResult(BaseModel):
    blocks: List[ImageBlock] = Field(default_factory=list, description="图片中的文本块翻译结果")
    full_text: Optional[str] = Field(None, description="合并后的完整译文")

class ImageTranslateResponse(BaseModel):
    status: str = Field("success", description="请求状态")
    service: str = Field("image-translation", description="服务名称")
    result: ImageTranslateResult

# --- Term Schemas ---
class TermRequest(BaseModel):
    text: str

class TermItem(BaseModel):
    source: str
    target: str

class TermResponse(BaseModel):
    terms: List[TermItem]

# --- PDF Translation Schemas ---
class PDFTranslateResponse(BaseModel):
    success: bool
    markdown: Optional[str] = None
    error: Optional[str] = None

