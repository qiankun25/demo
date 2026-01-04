from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application configuration using Pydantic Settings.
    
    All settings can be configured via environment variables.
    """
    
    # Application
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_workers: int = 4
    
    # Database
    database_url: str
    
    # Redis
    redis_url: str = "redis://localhost:6379/0"
    
    # MinIO/S3
    minio_endpoint: str
    minio_external_endpoint: Optional[str] = None  # External endpoint for presigned URLs
    minio_access_key: str
    minio_secret_key: str
    minio_bucket: str = "papers"
    minio_secure: bool = False
    aws_region: Optional[str] = None
    
    # Celery
    celery_broker_url: Optional[str] = None
    celery_result_backend: Optional[str] = None
    celery_worker_concurrency: int = 4
    
    # Download settings
    max_file_size: int = 104857600  # 100MB
    download_timeout: int = 300  # 5 minutes
    max_retries: int = 3
    user_agent: str = "Mozilla/5.0 (compatible; LiteratureBot/1.0)"
    
    # Downloader service settings
    downloader_timeout: int = 30  # Timeout for PDF downloader (seconds)
    downloader_chunk_size: int = 8192  # Chunk size for streaming downloads (bytes)
    
    # URL validator settings
    validator_timeout: int = 10  # Timeout for URL validation (seconds)
    
    # Presigned URL settings
    presigned_url_expires: int = 3600  # Default presigned URL expiration (seconds, 1 hour)
    presigned_url_min_expires: int = 60  # Minimum presigned URL expiration (seconds)
    presigned_url_max_expires: int = 86400  # Maximum presigned URL expiration (seconds, 24 hours)
    
    # Retry settings
    retry_backoff_base: int = 5  # Base delay for exponential backoff (seconds)
    retry_backoff_max: int = 600  # Maximum delay for exponential backoff (seconds)
    
    # Celery task settings
    celery_task_default_retry_delay: int = 5  # Default retry delay for Celery tasks (seconds)
    celery_task_time_limit: int = 300  # Hard time limit for Celery tasks (seconds, 5 minutes)
    celery_task_soft_time_limit: int = 240  # Soft time limit for Celery tasks (seconds, 4 minutes)
    
    # Database connection pool settings
    db_pool_size: int = 20  # Database connection pool size
    db_max_overflow: int = 10  # Maximum overflow connections for database pool
    
    # AWS/S3 region (default for MinIO)
    aws_region_default: str = "us-east-1"  # Default AWS region for MinIO
    
    # API settings
    api_rate_limit: int = 100
    cors_origins: str = "*"
    api_key_header: str = "X-API-Key"
    allowed_api_keys: str = ""
    
    # Logging
    log_level: str = "INFO"
    log_format: str = "json"
    
    # Webhook (optional)
    webhook_url: Optional[str] = None
    webhook_secret: Optional[str] = None
    
    # Monitoring (optional)
    sentry_dsn: Optional[str] = None
    sentry_environment: Optional[str] = None
    enable_metrics: bool = False
    metrics_port: int = 9090
    
    @property
    def aws_region_value(self) -> str:
        """Get AWS region value, using aws_region if set, otherwise default."""
        return self.aws_region or self.aws_region_default
    
    class Config:
        env_file = ".env"
        case_sensitive = False
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Set Celery URLs from Redis URL if not explicitly provided
        if self.celery_broker_url is None:
            self.celery_broker_url = self.redis_url.replace("/0", "/0")
        if self.celery_result_backend is None:
            self.celery_result_backend = self.redis_url.replace("/0", "/1")
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.app_env.lower() == "production"
    
    @property
    def cors_origins_list(self) -> list[str]:
        """Get CORS origins as a list."""
        if self.cors_origins == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]
    
    @property
    def api_keys_list(self) -> list[str]:
        """Get allowed API keys as a list."""
        if not self.allowed_api_keys:
            return []
        return [key.strip() for key in self.allowed_api_keys.split(",") if key.strip()]


# Global settings instance
settings = Settings()
