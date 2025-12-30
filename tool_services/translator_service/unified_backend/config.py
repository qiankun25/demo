import os
from pydantic_settings import BaseSettings
from typing import List

def _legacy_siliconflow_config() -> dict:
    """
    兼容旧 translator_service：旧实现把 SiliconFlow key/model 写在 nexus_tool/config.py。
    新 unified_backend 优先使用环境变量；若未设置，则回退读取旧配置（在单独运行 unified_backend 时不会报错）。
    """
    try:
        from nexus_tool import config as legacy  # type: ignore

        return {
            "api_key": getattr(legacy, "SILICONFLOW_API_KEY", "") or "",
            "api_base": getattr(legacy, "API_BASE", "") or "https://api.siliconflow.cn/v1/chat/completions",
            "model": getattr(legacy, "DEFAULT_MODEL", "") or "deepseek-ai/DeepSeek-V3",
        }
    except Exception:
        return {
            "api_key": "",
            "api_base": "https://api.siliconflow.cn/v1/chat/completions",
            "model": "deepseek-ai/DeepSeek-V3",
        }


_legacy = _legacy_siliconflow_config()


class Settings(BaseSettings):
    # 应用基础配置
    APP_NAME: str = "Academic Translator Unified Service"
    TITLE: str = "Academic Translator Unified Service"
    DESCRIPTION: str = "学术翻译统一服务，集成文本、图片、术语及 PDF 翻译功能"
    VERSION: str = "1.0.0"
    DEBUG: bool = False
    
    # 运行配置
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # 核心 API 配置
    DASHSCOPE_API_KEY: str = os.getenv("DASHSCOPE_API_KEY", "")

    # SiliconFlow（用于在未配置 DashScope 时做文本翻译回退；也可被旧 /translate 复用）
    SILICONFLOW_API_KEY: str = os.getenv("SILICONFLOW_API_KEY", "") or _legacy["api_key"]
    SILICONFLOW_API_BASE: str = os.getenv("SILICONFLOW_API_BASE", "") or _legacy["api_base"]
    SILICONFLOW_MODEL: str = os.getenv("SILICONFLOW_MODEL", "") or _legacy["model"]
    
    # 百度图片翻译配置（建议通过环境变量注入；此处保留默认值以兼容旧逻辑）
    BAIDU_APP_ID: str = os.getenv("BAIDU_APP_ID", "20251210002516271")
    BAIDU_SECRET_KEY: str = os.getenv("BAIDU_SECRET_KEY", "H6gn6L1uEQgSkDq8f13G")
    
    # 临时文件目录
    TMP_DIR: str = "./temp"
    IMAGE_TMP_DIR: str = "./temp/images"
    
    # 日志配置
    LOG_LEVEL: str = "INFO"
    
    # CORS配置
    CORS_ORIGINS: List[str] = ["*"]
    CORS_ALLOW_CREDENTIALS: bool = True
    CORS_ALLOW_METHODS: List[str] = ["*"]
    CORS_ALLOW_HEADERS: List[str] = ["*"]
    
    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()

