from fastapi import APIRouter, HTTPException, status, UploadFile, File, Form
from pydantic import BaseModel
from typing import Dict, Any, Optional
import requests
import asyncio
from config import settings

router = APIRouter(prefix="/api", tags=["Literature Translation"])

# Configuration
TRANSLATOR_SERVICE_BASE_URL = settings.TRANSLATOR_SERVICE_BASE_URL


class TranslatePaperMeta(BaseModel):
    """翻译元信息"""
    target_lang: str
    file_name: str
    model: str


class TranslatePaperResponse(BaseModel):
    """论文翻译响应"""
    text_translated: str
    meta: TranslatePaperMeta


@router.post("/translate-paper", response_model=TranslatePaperResponse)
async def translate_paper(
    file: UploadFile = File(...),
    target_lang: str = Form("zh")
):
    """
    翻译论文文件
    
    调用 Translator Service 的 /api/v1/translate/image API 进行文件翻译
    
    请求参数（multipart/form-data）：
    - file: 论文文件（.pdf）
    - target_lang: 目标语言代码（如 "zh"、"en"），默认为 "zh"
    
    返回：
    - text_translated: 提取并翻译后的完整论文文本
    - meta: 元信息，包含 target_lang, file_name, model
    """
    # 验证文件类型（只支持 PDF）
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error": "only PDF files are supported"}
        )
    
    try:
        # 读取文件内容
        file_contents = await file.read()
        
        # 准备文件数据
        files = {
            'file': (file.filename, file_contents, file.content_type)
        }
        
        # 准备表单数据（包含 target_lang）
        data = {
            'target_lang': target_lang
        }
        
        # 调用 Translator Service
        def _translate():
            response = requests.post(
                f"{settings.TRANSLATOR_SERVICE_BASE_URL}/api/v1/translate/image",
                files=files,
                data=data,
                timeout=120  # 翻译可能需要较长时间
            )
            response.raise_for_status()
            return response.json()
        
        result = await asyncio.to_thread(_translate)
        
        # 转换响应格式以匹配新的规范
        # 假设 Translator Service 返回的格式包含翻译文本
        # 需要根据实际 Translator Service 的响应格式进行调整
        translated_text = result.get("result", {}).get("full_text", "") or result.get("text_translated", "")
        
        # 获取模型信息（如果 Translator Service 返回）
        model = result.get("model", "deepseek-ai/DeepSeek-V3")
        
        return TranslatePaperResponse(
            text_translated=translated_text,
            meta=TranslatePaperMeta(
                target_lang=target_lang,
                file_name=file.filename,
                model=model
            )
        )
        
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 400:
            error_detail = e.response.json().get("error") or e.response.json().get("detail", "请求参数错误")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": error_detail}
            )
        elif e.response.status_code in [500, 502]:
            error_detail = e.response.text if hasattr(e, 'response') else str(e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": f"PDF parsing failed: {error_detail}"}
            )
        else:
            error_detail = e.response.text if hasattr(e, 'response') else str(e)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error": f"翻译失败: {error_detail}"}
            )
    except requests.exceptions.Timeout:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail={"error": "翻译服务超时，请稍后重试"}
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": f"PDF parsing failed: {str(e)}"}
        )

