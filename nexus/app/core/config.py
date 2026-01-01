"""Configuration management using pydantic-settings

This module provides centralized configuration for the Nexus Orchestration Service,
loading settings from environment variables with sensible defaults for local development.

Requirements: 13.1, 13.2, 13.3, 13.4
"""

from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables
    
    All settings can be overridden via environment variables.
    Boolean values accept: "true", "1", "yes" for True; "false", "0", "no" for False.
    """
    
    # RabbitMQ Configuration (Requirement 13.1)
    rabbitmq_url: str = Field(
        default="amqp://guest:guest@localhost:5672/",
        description="RabbitMQ connection URL"
    )
    cmd_exchange: str = Field(
        default="nexus.cmd.exchange",
        description="Command exchange name for direct routing"
    )
    evt_exchange: str = Field(
        default="nexus.evt.exchange",
        description="Event exchange name for topic routing"
    )
    dlx_exchange: str = Field(
        default="nexus.dlx.exchange",
        description="Dead letter exchange for failed messages"
    )
    event_queue: str = Field(
        default="nexus.events",
        description="Queue name for consuming events"
    )
    
    # MinIO Configuration (Requirement 13.2)
    minio_endpoint: str = Field(
        default="localhost:9000",
        description="MinIO server endpoint"
    )
    minio_access_key: str = Field(
        default="minioadmin",
        description="MinIO access key"
    )
    minio_secret_key: str = Field(
        default="minioadmin",
        description="MinIO secret key"
    )
    minio_bucket: str = Field(
        default="papers",
        description="MinIO bucket name for storage"
    )
    minio_secure: bool = Field(
        default=False,
        description="Use HTTPS for MinIO connection"
    )
    storage_prefix: str = Field(
        default="claimcheck/",
        description="Prefix for claim-check storage keys"
    )
    
    # Service Configuration (Requirement 13.3)
    service_name: str = Field(
        default="nexus",
        description="Service identifier for logging and tracing"
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)"
    )
    max_concurrent_jobs: int = Field(
        default=100,
        description="Maximum number of concurrent jobs to process"
    )
    shutdown_timeout: int = Field(
        default=30,
        description="Graceful shutdown timeout in seconds"
    )
    
    # Workflow Configuration
    workflow_config_path: str = Field(
        default="config/workflows.yaml",
        description="Path to workflow definitions YAML file"
    )
    
    # Retry Configuration
    max_retry_attempts: int = Field(
        default=3,
        description="Maximum retry attempts for transient failures"
    )
    retry_initial_delay: float = Field(
        default=1.0,
        description="Initial delay for exponential backoff (seconds)"
    )
    retry_max_delay: float = Field(
        default=30.0,
        description="Maximum delay for exponential backoff (seconds)"
    )
    retry_exponential_base: float = Field(
        default=2.0,
        description="Base for exponential backoff calculation"
    )
    
    # API Configuration
    api_host: str = Field(
        default="0.0.0.0",
        description="API server host"
    )
    api_port: int = Field(
        default=8000,
        description="API server port"
    )
    api_prefix: str = Field(
        default="/api/v1",
        description="API route prefix"
    )

    # Downstream Query APIs (used for report aggregation in strict microservices mode)
    discovery_base_url: str = Field(default="http://localhost:8000", description="Discovery service API base URL")
    download_base_url: str = Field(default="http://localhost:8001", description="Download service API base URL")
    parser_base_url: str = Field(default="http://localhost:8031", description="Parser service API base URL")
    indexing_base_url: str = Field(default="http://localhost:8020", description="Indexing service API base URL")
    overview_base_url: str = Field(default="http://localhost:8040", description="Overview service API base URL")

    # Orchestration DB (strict microservices migration)
    database_url: str = Field(
        default="sqlite:///./orchestration.db",
        description="SQLAlchemy database URL for orchestration state (jobs/work_items/artifacts/outbox/inbox)",
    )
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )


# Global settings instance
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Get or create the global settings instance
    
    Returns:
        Settings: The application settings
    """
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings
