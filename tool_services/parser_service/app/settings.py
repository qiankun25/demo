from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    # MQ
    rabbitmq_url: str = Field(default="amqp://guest:guest@localhost:5672/")
    cmd_exchange: str = Field(default="nexus.cmd.exchange")
    evt_exchange: str = Field(default="nexus.evt.exchange")
    cmd_routing_key: str = Field(default="cmd.parser.start")
    queue_name: str = Field(default="q.parser.worker")

    # DB
    database_url: str = Field(default="postgresql://parser_user:parser_pass@localhost:5435/parser")

    # Upstreams
    download_base_url: str = Field(default="http://localhost:8001")
    download_signed_url_path_tpl: str = Field(default="/files/{file_id}/signed_url")
    http_timeout: float = Field(default=60.0)

    # Storage (MinIO)
    minio_endpoint: str = Field(default="localhost:9000")
    minio_access_key: str = Field(default="minioadmin")
    minio_secret_key: str = Field(default="minioadmin")
    minio_bucket: str = Field(default="papers")
    minio_secure: bool = Field(default=False)
    minio_prefix: str = Field(default="parser/")

    class Config:
        env_prefix = "PARSER_"
        case_sensitive = False


settings = Settings()


