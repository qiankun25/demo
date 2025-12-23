from datetime import date, timedelta
from typing import Dict, Any


def encode_filters(filters: Dict[str, Any]) -> str:
    """
    将 {field: value|list} 编码为 OpenAlex filter 字符串。
    列表/元组会用 '|' 连接；字符串保留原值。

    支持的“友好字段”（会转换为 OpenAlex 支持的字段）：
    - last_n_days -> from_publication_date:YYYY-MM-DD
    - from_date -> from_publication_date
    - to_date -> to_publication_date
    - journal -> primary_location.source.display_name.search
    - issn -> primary_location.source.issn
    """
    if not filters:
        return ""

    normalized = normalize_filters(filters)
    parts = []
    for k, v in normalized.items():
        if v is None:
            continue
        if isinstance(v, (list, tuple)):
            val = "|".join(str(x) for x in v)
        else:
            val = str(v)
        parts.append(f"{k}:{val}")
    return ",".join(parts)


def normalize_filters(filters: Dict[str, Any]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}

    def _is_empty(x: Any) -> bool:
        if x is None:
            return True
        if isinstance(x, str) and not x.strip():
            return True
        if isinstance(x, (list, tuple, dict)) and len(x) == 0:
            return True
        return False

    src = dict(filters or {})

    # 时间：最近 N 天
    last_n_days = src.pop("last_n_days", None)
    if not _is_empty(last_n_days):
        try:
            n = int(last_n_days)
            if n > 0:
                out["from_publication_date"] = (date.today() - timedelta(days=n)).isoformat()
        except Exception:
            pass

    # 日期范围
    from_date = src.pop("from_date", None)
    to_date = src.pop("to_date", None)
    if not _is_empty(from_date):
        out["from_publication_date"] = str(from_date).strip()
    if not _is_empty(to_date):
        out["to_publication_date"] = str(to_date).strip()

    # 允许直接传 OpenAlex 字段
    from_pub = src.pop("from_publication_date", None)
    to_pub = src.pop("to_publication_date", None)
    if not _is_empty(from_pub):
        out["from_publication_date"] = str(from_pub).strip()
    if not _is_empty(to_pub):
        out["to_publication_date"] = str(to_pub).strip()

    # Venue
    journal = src.pop("journal", None)
    if not _is_empty(journal):
        out["primary_location.source.display_name.search"] = str(journal).strip()

    issn = src.pop("issn", None)
    if not _is_empty(issn):
        if isinstance(issn, (list, tuple)):
            out["primary_location.source.issn"] = [str(x).strip() for x in issn if not _is_empty(x)]
        else:
            out["primary_location.source.issn"] = str(issn).strip()

    # 其余字段透传
    for k, v in src.items():
        if _is_empty(v):
            continue
        out[str(k)] = v

    return out

