from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    # 数据库配置 - 优先使用 DATABASE_URL，如果没有则使用单独配置
    DATABASE_URL: Optional[str] = None
    
    # 单独配置项（当 DATABASE_URL 未设置时使用）
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = ""
    DB_NAME: str = "wfw_db"
    
    # 后端API基础URL和主机
    API_BASE_URL: str = "http://8.134.183.68:8000/api/v1"
    BASE_HOST: str = "http://8.134.183.68:8000"
    
    # 翻译服务基础URL
    TRANSLATOR_SERVICE_BASE_URL: str = "http://8.134.183.68:8002"
    
    # 索引服务基础URL
    INDEXING_SERVICE_BASE_URL: str = "http://8.134.183.68:8020"
    
    # MinIO上传服务器URL
    MINIO_UPLOAD_URL: str = "http://8.134.183.68:8001/upload"
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True


settings = Settings()

