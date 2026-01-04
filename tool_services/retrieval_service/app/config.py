"""
Configuration module for retrieval service.
Loads configuration from config.yaml and environment variables.
"""
import os
import yaml
from pathlib import Path
from typing import Any, Dict, Optional
from pydantic import Field
from pydantic_settings import BaseSettings


def _load_yaml_config(config_path: Optional[str] = None) -> Dict[str, Any]:
    """Load configuration from YAML file."""
    if config_path is None:
        # Default to config.yaml in service root
        service_root = Path(__file__).parent.parent
        config_path = service_root / "config.yaml"
    else:
        config_path = Path(config_path)
    
    if not config_path.exists():
        return {}
    
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _get_nested_value(config: Dict[str, Any], key_path: str, default: Any = None) -> Any:
    """Get nested value from config dict using dot notation."""
    keys = key_path.split(".")
    value = config
    for key in keys:
        if isinstance(value, dict):
            value = value.get(key)
            if value is None:
                return default
        else:
            return default
    return value


class Settings(BaseSettings):
    """Application settings with YAML config support."""
    
    # Config file path (can be overridden by env var)
    config_file: Optional[str] = Field(default=None, description="Path to config.yaml")
    
    # Load YAML config
    _yaml_config: Dict[str, Any] = {}
    
    def __init__(self, **kwargs):
        # Load YAML config first
        config_file = kwargs.pop("config_file", None) or os.getenv("RETRIEVAL_CONFIG_FILE")
        self._yaml_config = _load_yaml_config(config_file)
        
        # Set defaults from YAML
        defaults = {}
        
        # Service config
        defaults["service_name"] = _get_nested_value(self._yaml_config, "service.name", "retrieval_service")
        defaults["service_host"] = _get_nested_value(self._yaml_config, "service.host", "0.0.0.0")
        defaults["service_port"] = _get_nested_value(self._yaml_config, "service.port", 8003)
        defaults["service_version"] = _get_nested_value(self._yaml_config, "service.version", "0.1.0")
        defaults["service_title"] = _get_nested_value(self._yaml_config, "service.title", "Retrieval Service")
        defaults["service_description"] = _get_nested_value(
            self._yaml_config, "service.description", "统一检索编排层 + 事件驱动入库状态机"
        )
        
        # Upstreams
        defaults["discovery_base_url"] = _get_nested_value(
            self._yaml_config, "upstreams.discovery_base_url", "http://localhost:8000"
        )
        defaults["download_base_url"] = _get_nested_value(
            self._yaml_config, "upstreams.download_base_url", "http://localhost:8001"
        )
        defaults["parser_base_url"] = _get_nested_value(
            self._yaml_config, "upstreams.parser_base_url", "http://localhost:3000"
        )
        defaults["indexing_base_url"] = _get_nested_value(
            self._yaml_config, "upstreams.indexing_base_url", "http://localhost:8020"
        )
        
        # Credentials
        defaults["kaggle_username"] = _get_nested_value(self._yaml_config, "credentials.kaggle_username")
        defaults["kaggle_key"] = _get_nested_value(self._yaml_config, "credentials.kaggle_key")
        defaults["github_token"] = _get_nested_value(self._yaml_config, "credentials.github_token")
        
        # Database
        defaults["db_path"] = _get_nested_value(self._yaml_config, "database.db_path", "retrieval.db")
        index_db_path = _get_nested_value(self._yaml_config, "database.index_db_path")
        if not index_db_path:
            # Default to ../indexing_service/index.db
            service_root = Path(__file__).parent.parent
            index_db_path = service_root.parent / "indexing_service" / "index.db"
            defaults["index_db_path"] = str(index_db_path)
        else:
            defaults["index_db_path"] = index_db_path
        
        defaults["sqlite_timeout"] = _get_nested_value(self._yaml_config, "database.sqlite_timeout", 30.0)
        
        # HTTP
        defaults["http_timeout"] = _get_nested_value(self._yaml_config, "http.timeout", 30.0)
        defaults["health_check_timeout"] = _get_nested_value(self._yaml_config, "http.health_check_timeout", 5.0)
        
        # Retrieval strategy
        defaults["local_first"] = _get_nested_value(self._yaml_config, "retrieval.local_first", True)
        defaults["min_local_hits"] = _get_nested_value(self._yaml_config, "retrieval.min_local_hits", 5)
        defaults["min_local_score"] = _get_nested_value(self._yaml_config, "retrieval.min_local_score", 0.01)
        defaults["ingest_external_hits"] = _get_nested_value(self._yaml_config, "retrieval.ingest_external_hits", True)
        defaults["local_scan_limit"] = _get_nested_value(self._yaml_config, "retrieval.local_scan_limit", 50)
        defaults["semantic_search_k_multiplier"] = _get_nested_value(
            self._yaml_config, "retrieval.semantic_search_k_multiplier", 3
        )
        defaults["semantic_search_max_k"] = _get_nested_value(
            self._yaml_config, "retrieval.semantic_search_max_k", 50
        )
        
        # Download polling
        defaults["download_poll_interval"] = _get_nested_value(
            self._yaml_config, "download_polling.poll_interval", 5.0
        )
        defaults["download_max_polls"] = _get_nested_value(self._yaml_config, "download_polling.max_polls", 60)
        
        # Worker
        defaults["worker_enabled"] = _get_nested_value(self._yaml_config, "worker.enabled", True)
        defaults["worker_poll_interval"] = _get_nested_value(self._yaml_config, "worker.poll_interval", 1.0)
        defaults["max_event_attempts"] = _get_nested_value(self._yaml_config, "worker.max_event_attempts", 5)
        defaults["retry_delay_base"] = _get_nested_value(self._yaml_config, "worker.retry_delay_base", 60)
        defaults["retry_backoff_exponent"] = _get_nested_value(
            self._yaml_config, "worker.retry_backoff_exponent", 2
        )
        
        # Chroma
        defaults["chroma_collection"] = _get_nested_value(
            self._yaml_config, "chroma.collection", "paper_chunks"
        )
        defaults["chroma_distance"] = _get_nested_value(self._yaml_config, "chroma.distance", "cosine")
        defaults["embed_dim"] = _get_nested_value(self._yaml_config, "chroma.embed_dim", 256)
        chroma_persist_dir = _get_nested_value(self._yaml_config, "chroma.persist_dir")
        if not chroma_persist_dir:
            service_root = Path(__file__).parent.parent
            chroma_persist_dir = service_root.parent / "indexing_service" / "chroma_data"
            defaults["chroma_persist_dir"] = str(chroma_persist_dir)
        else:
            defaults["chroma_persist_dir"] = chroma_persist_dir
        
        # Hashing
        defaults["event_id_length"] = _get_nested_value(self._yaml_config, "hashing.event_id_length", 24)
        defaults["doc_key_hash_length"] = _get_nested_value(
            self._yaml_config, "hashing.doc_key_hash_length", 32
        )
        defaults["doc_id_hash_length"] = _get_nested_value(self._yaml_config, "hashing.doc_id_hash_length", 32)
        defaults["query_id_hash_length"] = _get_nested_value(
            self._yaml_config, "hashing.query_id_hash_length", 24
        )
        
        # Merge defaults with kwargs (env vars take precedence)
        for key, value in defaults.items():
            if key not in kwargs:
                kwargs[key] = value
        
        super().__init__(**kwargs)
    
    # Service config
    service_name: str
    service_host: str
    service_port: int
    service_version: str
    service_title: str
    service_description: str
    
    # Upstreams
    discovery_base_url: str
    download_base_url: str
    parser_base_url: str
    indexing_base_url: str
    
    # Credentials
    kaggle_username: Optional[str] = None
    kaggle_key: Optional[str] = None
    github_token: Optional[str] = None
    
    # Database
    db_path: str
    index_db_path: str
    sqlite_timeout: float
    
    # HTTP
    http_timeout: float
    health_check_timeout: float
    
    # Retrieval strategy
    local_first: bool
    min_local_hits: int
    min_local_score: float
    ingest_external_hits: bool
    local_scan_limit: int
    semantic_search_k_multiplier: int
    semantic_search_max_k: int
    
    # Download polling
    download_poll_interval: float
    download_max_polls: int
    
    # Worker
    worker_enabled: bool
    worker_poll_interval: float
    max_event_attempts: int
    retry_delay_base: int
    retry_backoff_exponent: int
    
    # Chroma
    chroma_collection: str
    chroma_distance: str
    embed_dim: int
    chroma_persist_dir: str
    
    # Hashing
    event_id_length: int
    doc_key_hash_length: int
    doc_id_hash_length: int
    query_id_hash_length: int
    
    @property
    def constants(self) -> Dict[str, Any]:
        """Get constants from YAML config."""
        return _get_nested_value(self._yaml_config, "constants", {})
    
    @property
    def limits(self) -> Dict[str, Any]:
        """Get limits from YAML config."""
        return _get_nested_value(self._yaml_config, "limits", {})
    
    @property
    def cors_config(self) -> Dict[str, Any]:
        """Get CORS config from YAML."""
        return _get_nested_value(self._yaml_config, "cors", {})
    
    @property
    def text_processing(self) -> Dict[str, Any]:
        """Get text processing config from YAML."""
        return _get_nested_value(self._yaml_config, "text_processing", {})
    
    class Config:
        env_prefix = "RETRIEVAL_"
        case_sensitive = False
        extra = "ignore"


# Global settings instance
settings = Settings()

