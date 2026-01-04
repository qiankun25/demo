from __future__ import annotations

from typing import Iterable, List, Optional, Sequence, Set

from pydantic import BaseSettings, Field, SettingsConfigDict, validator


def _default_select_fields() -> str:
    return ",".join(
        [
            "id",
            "doi",
            "display_name",
            "title",
            "publication_year",
            "publication_date",
            "type",
            "cited_by_count",
            "open_access",
            "best_oa_location",
            "primary_location",
            "locations",
            "authorships",
        ]
    )


class DiscoverySettings(BaseSettings):
    """Shared configuration for the discovery microservice."""

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=False)

    discovery_database_url: Optional[str] = Field(None, env="DISCOVERY_DATABASE_URL")
    discovery_db_url: Optional[str] = Field(None, env="DISCOVERY_DB_URL")

    rabbitmq_url: str = Field("amqp://guest:guest@localhost:5672/", env="RABBITMQ_URL")
    nexus_cmd_exchange: str = Field("nexus.cmd.exchange", env="NEXUS_CMD_EXCHANGE")
    nexus_evt_exchange: str = Field("nexus.evt.exchange", env="NEXUS_EVT_EXCHANGE")
    discovery_cmd_routing_key: str = Field("cmd.discovery.start", env="DISCOVERY_CMD_ROUTING_KEY")
    discovery_cmd_queue: str = Field("q.discovery.worker", env="DISCOVERY_CMD_QUEUE")
    nexus_prefetch: int = Field(4, env="NEXUS_PREFETCH")
    log_level: str = Field("INFO", env="LOG_LEVEL")

    openalex_base: str = Field("https://api.openalex.org", env="OPENALEX_BASE")
    openalex_works_path: str = Field("/works", env="OPENALEX_WORKS_PATH")
    openalex_timeout_s: float = Field(20.0, env="OPENALEX_TIMEOUT_S")
    openalex_max_retries: int = Field(5, env="OPENALEX_MAX_RETRIES")
    openalex_backoff_base_s: float = Field(1.0, env="OPENALEX_BACKOFF_BASE_S")
    openalex_backoff_max_s: float = Field(30.0, env="OPENALEX_BACKOFF_MAX_S")
    openalex_backoff_jitter_ratio: float = Field(0.2, env="OPENALEX_BACKOFF_JITTER_RATIO")
    openalex_user_agent: str = Field("demo-openalex-client", env="OPENALEX_USER_AGENT")
    openalex_mailto: str = Field("", env="OPENALEX_MAILTO")
    openalex_retryable_status_codes: List[int] = Field(
        default_factory=lambda: [429, 500, 502, 503, 504, 408],
        env="OPENALEX_RETRYABLE_STATUS_CODES",
    )
    openalex_rate_limit_rps: float = Field(0.0, env="OPENALEX_RATE_LIMIT_RPS")
    openalex_rate_limit_burst: int = Field(0, env="OPENALEX_RATE_LIMIT_BURST")
    openalex_max_concurrency: int = Field(0, env="OPENALEX_MAX_CONCURRENCY")
    openalex_quota_per_minute: int = Field(0, env="OPENALEX_QUOTA_PER_MINUTE")
    openalex_quota_per_day: int = Field(0, env="OPENALEX_QUOTA_PER_DAY")

    discovery_strict_validation: bool = Field(False, env="DISCOVERY_STRICT_VALIDATION")
    discovery_strict_filters: bool = Field(False, env="DISCOVERY_STRICT_FILTERS")
    discovery_strict_select: bool = Field(False, env="DISCOVERY_STRICT_SELECT")
    discovery_strict_mailto: bool = Field(False, env="DISCOVERY_STRICT_MAILTO")

    discovery_limit_max: int = Field(200, env="DISCOVERY_LIMIT_MAX")
    discovery_max_last_n_days: int = Field(3650, env="DISCOVERY_MAX_LAST_N_DAYS")
    discovery_select_allowlist: str = Field("", env="DISCOVERY_SELECT_ALLOWLIST")
    discovery_select_max_fields: int = Field(0, env="DISCOVERY_SELECT_MAX_FIELDS")
    discovery_select_max_len: int = Field(0, env="DISCOVERY_SELECT_MAX_LEN")
    discovery_filters_max_keys: int = Field(0, env="DISCOVERY_FILTERS_MAX_KEYS")
    discovery_filters_max_list_len: int = Field(0, env="DISCOVERY_FILTERS_MAX_LIST_LEN")
    discovery_filters_max_value_len: int = Field(0, env="DISCOVERY_FILTERS_MAX_VALUE_LEN")
    discovery_postfilter_multiplier: int = Field(3, env="DISCOVERY_POSTFILTER_MULTIPLIER")

    discovery_redis_url: str = Field("", env="DISCOVERY_REDIS_URL")
    redis_url: str = Field("", env="REDIS_URL")
    discovery_cache_ttl_s: int = Field(3600, env="DISCOVERY_CACHE_TTL_S")
    discovery_cache_prefix: str = Field("nexus:discovery:v1", env="DISCOVERY_CACHE_PREFIX")

    default_select: str = Field(_default_select_fields(), env="DEFAULT_SELECT")

    @validator("openalex_retryable_status_codes", pre=True)
    def _deserialize_retryable_status_codes(cls, value: Optional[Sequence[int | str]]) -> List[int]:
        if value is None:
            return []
        if isinstance(value, str):
            parts = [item.strip() for item in value.split(",") if item.strip()]
            return [int(part) for part in parts if part.isdigit()]
        return [int(item) for item in value]

    @property
    def database_url(self) -> str:
        default = "postgresql://discovery_user:discovery_pass@localhost:5434/discovery"
        return self.discovery_database_url or self.discovery_db_url or default

    @property
    def redis_connection_url(self) -> str:
        return self.discovery_redis_url or self.redis_url or ""

    @property
    def select_allowlist_values(self) -> List[str]:
        return [part.strip() for part in self.discovery_select_allowlist.split(",") if part.strip()]


settings = DiscoverySettings()

