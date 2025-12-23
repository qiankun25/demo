import os

# OpenAlex
OPENALEX_BASE = os.getenv("OPENALEX_BASE", "https://api.openalex.org")
OPENALEX_WORKS_PATH = "/works"
OPENALEX_TIMEOUT_S = float(os.getenv("OPENALEX_TIMEOUT_S", "20"))
OPENALEX_MAX_RETRIES = int(os.getenv("OPENALEX_MAX_RETRIES", "5"))
OPENALEX_BACKOFF_BASE_S = float(os.getenv("OPENALEX_BACKOFF_BASE_S", "1.0"))
OPENALEX_USER_AGENT = os.getenv("OPENALEX_USER_AGENT", "demo-openalex-client")

# polite pool（建议设置为你自己的邮箱）
OPENALEX_MAILTO = os.getenv("OPENALEX_MAILTO", "")

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

