import os
from typing import Dict, Any, List, Optional

from pydantic import Field
from pydantic_settings import BaseSettings


def _service_root_dir() -> str:
    """Stable base dir for resolving relative paths.

    - Repo layout: tool_services/indexing_service/app/core/config.py -> ../../ = tool_services/indexing_service
    - Container layout (Dockerfile copies service to /app): /app/app/core/config.py -> ../../ = /app
    """
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _normalize_fs_path(path: str) -> str:
    path = (path or "").strip()
    if not path:
        return path
    if os.path.isabs(path):
        return path
    return os.path.abspath(os.path.join(_service_root_dir(), path))


def _normalize_database_url(url: str) -> str:
    """Deprecated: Postgres-only in P0."""
    url = (url or "").strip()
    if not url:
        return url
    return url


class Settings(BaseSettings):
    # API Settings
    PROJECT_NAME: str = "Indexing Service"
    VERSION: str = "0.2.0"
    
    # Database Settings
    # P0: Postgres-only
    DATABASE_URL: str = Field("postgresql://index_user:index_pass@localhost:5436/indexing", description="Database connection string")
    
    # Embedding Settings
    EMBED_DIM: int = Field(256, ge=32, le=2048, description="向量维度（hash embedding）")
    
    # Chroma Settings
    CHROMA_PERSIST_DIR: str = Field(".chroma", description="Chroma 持久化目录")
    CHROMA_COLLECTION: str = Field("morning_report", description="Chroma collection 名称")
    CHROMA_DISTANCE: str = Field("cosine", description="Chroma HNSW space（cosine/l2/ip）")
    
    # RabbitMQ Settings
    RABBITMQ_URL: str = Field("amqp://guest:guest@localhost:5672/", description="RabbitMQ connection string")

    class Config:
        env_prefix = "INDEX_"
        case_sensitive = False
        extra = "ignore"

settings = Settings()

# Make defaults stable across processes by resolving relative fs paths.
settings.CHROMA_PERSIST_DIR = _normalize_fs_path(settings.CHROMA_PERSIST_DIR)

