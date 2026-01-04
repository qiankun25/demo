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
    PORT: int = Field(8020, description="API server port")
    
    # Database Settings
    # P0: Postgres-only
    DATABASE_URL: str = Field("postgresql://index_user:index_pass@localhost:5436/indexing", description="Database connection string")
    
    # Embedding Settings
    EMBED_DIM: int = Field(256, ge=32, le=2048, description="向量维度（hash embedding）")
    CONTENT_HASH_MAX_LENGTH: int = Field(2_000_000, description="内容哈希计算的最大长度限制")
    
    # Chroma Settings
    CHROMA_PERSIST_DIR: str = Field(".chroma", description="Chroma 持久化目录")
    CHROMA_COLLECTION: str = Field("morning_report", description="Chroma collection 名称")
    CHROMA_DISTANCE: str = Field("cosine", description="Chroma HNSW space（cosine/l2/ip）")
    
    # RabbitMQ Settings
    RABBITMQ_URL: str = Field("amqp://guest:guest@localhost:5672/", description="RabbitMQ connection string")
    NEXUS_CMD_EXCHANGE: str = Field("nexus.cmd.exchange", description="Nexus command exchange name")
    NEXUS_EVT_EXCHANGE: str = Field("nexus.evt.exchange", description="Nexus event exchange name")
    INDEX_CMD_ROUTING_KEY: str = Field("cmd.indexer.start", description="Indexer command routing key")
    INDEX_CMD_QUEUE: str = Field("q.index.worker", description="Indexer command queue name")
    NEXUS_PREFETCH: int = Field(4, ge=1, description="RabbitMQ prefetch count")
    EVT_INDEXER_FINISHED: str = Field("evt.indexer.finished", description="Indexer finished event routing key")
    EVT_INDEXER_FAILED: str = Field("evt.indexer.failed", description="Indexer failed event routing key")
    
    # External Service Settings
    INDEX_PARSER_BASE_URL: str = Field("http://localhost:8031", description="Parser service base URL")
    HTTP_CLIENT_TIMEOUT: float = Field(30.0, ge=1.0, description="HTTP client timeout in seconds")
    
    # MQ Worker Settings
    OUTBOX_BATCH_SIZE: int = Field(20, ge=1, description="Outbox event batch size for publishing")
    OUTBOX_POLL_INTERVAL: float = Field(0.2, ge=0.1, description="Outbox polling interval in seconds")
    
    # Search Settings
    RRF_K: int = Field(60, ge=1, description="Reciprocal Rank Fusion parameter k")
    SEARCH_MULTIPLIER: int = Field(3, ge=1, description="Search result multiplier for initial fetch")
    FTS_LANGUAGE: str = Field("english", description="Full-text search language for PostgreSQL")
    
    # KB Overview Settings
    KB_DEFAULT_LIMIT: int = Field(20, ge=1, description="Default limit for KB overview")
    KB_DEFAULT_OFFSET: int = Field(0, ge=0, description="Default offset for KB overview")
    KB_MAX_LIMIT: int = Field(200, ge=1, description="Maximum limit for KB overview")
    
    # CORS Settings
    CORS_ORIGINS: str = Field("*", description="CORS allowed origins (comma-separated or '*' for all)")
    
    # Logging Settings
    LOG_LEVEL: str = Field("INFO", description="Logging level")

    class Config:
        env_prefix = "INDEX_"
        case_sensitive = False
        extra = "ignore"

settings = Settings()

# Make defaults stable across processes by resolving relative fs paths.
settings.CHROMA_PERSIST_DIR = _normalize_fs_path(settings.CHROMA_PERSIST_DIR)

# Parse CORS origins
def get_cors_origins() -> List[str]:
    """Parse CORS origins from settings."""
    origins = settings.CORS_ORIGINS.strip()
    if origins == "*":
        return ["*"]
    return [origin.strip() for origin in origins.split(",") if origin.strip()]

