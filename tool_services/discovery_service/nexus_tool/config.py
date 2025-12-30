import os

# OpenAlex
OPENALEX_BASE = os.getenv("OPENALEX_BASE", "https://api.openalex.org")
OPENALEX_WORKS_PATH = "/works"
OPENALEX_TIMEOUT_S = float(os.getenv("OPENALEX_TIMEOUT_S", "20"))
OPENALEX_MAX_RETRIES = int(os.getenv("OPENALEX_MAX_RETRIES", "5"))
OPENALEX_BACKOFF_BASE_S = float(os.getenv("OPENALEX_BACKOFF_BASE_S", "1.0"))
OPENALEX_BACKOFF_MAX_S = float(os.getenv("OPENALEX_BACKOFF_MAX_S", "30"))
# 抖动比例：sleep = base*2^attempt + random()*ratio*(base*2^attempt)
OPENALEX_BACKOFF_JITTER_RATIO = float(os.getenv("OPENALEX_BACKOFF_JITTER_RATIO", "0.2"))
OPENALEX_USER_AGENT = os.getenv("OPENALEX_USER_AGENT", "demo-openalex-client")

# polite pool（建议设置为你自己的邮箱）
OPENALEX_MAILTO = os.getenv("OPENALEX_MAILTO", "")

# Retryable http status codes（逗号分隔）
OPENALEX_RETRYABLE_STATUS_CODES = os.getenv(
    "OPENALEX_RETRYABLE_STATUS_CODES", "429,500,502,503,504,408"
).strip()

# 请求限流/配额（可选；0/空表示不启用）
# - 仅作用于 discovery_service 进程内（若配置了 REDIS_URL，会用 Redis 做全局计数，跨进程更稳）
OPENALEX_RATE_LIMIT_RPS = float(os.getenv("OPENALEX_RATE_LIMIT_RPS", "0"))
OPENALEX_RATE_LIMIT_BURST = int(os.getenv("OPENALEX_RATE_LIMIT_BURST", "0"))
# 并发限制（可选；0 表示不限制）
OPENALEX_MAX_CONCURRENCY = int(os.getenv("OPENALEX_MAX_CONCURRENCY", "0"))
OPENALEX_QUOTA_PER_MINUTE = int(os.getenv("OPENALEX_QUOTA_PER_MINUTE", "0"))
OPENALEX_QUOTA_PER_DAY = int(os.getenv("OPENALEX_QUOTA_PER_DAY", "0"))

# 默认 select 精简字段（保持 download/index 能拿到 pdf_url/doi/title 等关键字段）
DEFAULT_SELECT = ",".join(
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

# 参数校验/规范化（默认尽量不破坏现有流程；需要更严格可通过环境变量开启）
DISCOVERY_STRICT_VALIDATION = os.getenv("DISCOVERY_STRICT_VALIDATION", "0").strip().lower() in (
    "1",
    "true",
    "yes",
    "y",
    "on",
)
DISCOVERY_STRICT_FILTERS = os.getenv("DISCOVERY_STRICT_FILTERS", "0").strip().lower() in (
    "1",
    "true",
    "yes",
    "y",
    "on",
)
DISCOVERY_STRICT_SELECT = os.getenv("DISCOVERY_STRICT_SELECT", "0").strip().lower() in (
    "1",
    "true",
    "yes",
    "y",
    "on",
)
DISCOVERY_STRICT_MAILTO = os.getenv("DISCOVERY_STRICT_MAILTO", "0").strip().lower() in (
    "1",
    "true",
    "yes",
    "y",
    "on",
)

DISCOVERY_LIMIT_MAX = int(os.getenv("DISCOVERY_LIMIT_MAX", "200"))
DISCOVERY_MAX_LAST_N_DAYS = int(os.getenv("DISCOVERY_MAX_LAST_N_DAYS", "3650"))

# select allowlist（可选；为空则不限制，仅做去重/规范化）
# 例：DISCOVERY_SELECT_ALLOWLIST="id,doi,title,publication_date"
DISCOVERY_SELECT_ALLOWLIST = os.getenv("DISCOVERY_SELECT_ALLOWLIST", "").strip()

# select 规范化限制（可选；<=0 表示不限制）
DISCOVERY_SELECT_MAX_FIELDS = int(os.getenv("DISCOVERY_SELECT_MAX_FIELDS", "0"))
DISCOVERY_SELECT_MAX_LEN = int(os.getenv("DISCOVERY_SELECT_MAX_LEN", "0"))

# filters 规范化限制（可选；<=0 表示不限制）
DISCOVERY_FILTERS_MAX_KEYS = int(os.getenv("DISCOVERY_FILTERS_MAX_KEYS", "0"))
DISCOVERY_FILTERS_MAX_LIST_LEN = int(os.getenv("DISCOVERY_FILTERS_MAX_LIST_LEN", "0"))
DISCOVERY_FILTERS_MAX_VALUE_LEN = int(os.getenv("DISCOVERY_FILTERS_MAX_VALUE_LEN", "0"))

# post-filter 拉取放大倍数：用于 journal/author 等本地过滤时增加 per_page，避免过滤后不足 limit
# 默认 3；设置为 1 表示不放大；设置为 0/负数会按 1 处理
DISCOVERY_POSTFILTER_MULTIPLIER = int(os.getenv("DISCOVERY_POSTFILTER_MULTIPLIER", "3"))

# Redis cache（可选；不配置则自动禁用缓存）
# 例：redis://redis:6379/0 或 redis://localhost:6379/0
REDIS_URL = (os.getenv("DISCOVERY_REDIS_URL") or os.getenv("REDIS_URL") or "").strip()
# 缓存有效期（秒）；<=0 表示不过期（不建议）
DISCOVERY_CACHE_TTL_S = int(os.getenv("DISCOVERY_CACHE_TTL_S", "3600"))
# key 前缀，便于不同环境隔离
DISCOVERY_CACHE_PREFIX = os.getenv("DISCOVERY_CACHE_PREFIX", "nexus:discovery:v1")

