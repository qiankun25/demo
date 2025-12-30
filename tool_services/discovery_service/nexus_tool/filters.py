from datetime import date, timedelta
import re
from typing import Dict, Any, Optional


_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def encode_filters(
    filters: Dict[str, Any],
    *,
    strict: bool = False,
    max_last_n_days: Optional[int] = None,
    max_keys: Optional[int] = None,
    max_list_len: Optional[int] = None,
    max_value_len: Optional[int] = None,
) -> str:
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

    normalized = normalize_filters(
        filters,
        strict=strict,
        max_last_n_days=max_last_n_days,
        max_keys=max_keys,
        max_list_len=max_list_len,
        max_value_len=max_value_len,
    )
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


def normalize_filters(
    filters: Dict[str, Any],
    *,
    strict: bool = False,
    max_last_n_days: Optional[int] = None,
    max_keys: Optional[int] = None,
    max_list_len: Optional[int] = None,
    max_value_len: Optional[int] = None,
) -> Dict[str, Any]:
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
    if max_keys is not None and max_keys > 0 and len(src) > max_keys:
        if strict:
            raise ValueError(f"too many filter keys: {len(src)} > {max_keys}")
        # non-strict: keep deterministic subset
        src = dict(list(src.items())[:max_keys])

    # 时间：最近 N 天
    last_n_days = src.pop("last_n_days", None)
    if not _is_empty(last_n_days):
        try:
            n = int(last_n_days)
            if max_last_n_days is not None and n > max_last_n_days:
                if strict:
                    raise ValueError(f"last_n_days too large: {n} > {max_last_n_days}")
                n = max_last_n_days
            if n > 0:
                out["from_publication_date"] = (date.today() - timedelta(days=n)).isoformat()
        except Exception:
            if strict:
                raise
            # 忽略非法值
            pass

    # 日期范围
    from_date = src.pop("from_date", None)
    to_date = src.pop("to_date", None)
    if not _is_empty(from_date):
        s = str(from_date).strip()
        if strict and not _ISO_DATE_RE.match(s):
            raise ValueError(f"from_date must be YYYY-MM-DD, got: {s!r}")
        out["from_publication_date"] = s
    if not _is_empty(to_date):
        s = str(to_date).strip()
        if strict and not _ISO_DATE_RE.match(s):
            raise ValueError(f"to_date must be YYYY-MM-DD, got: {s!r}")
        out["to_publication_date"] = s

    # 允许直接传 OpenAlex 字段
    from_pub = src.pop("from_publication_date", None)
    to_pub = src.pop("to_publication_date", None)
    if not _is_empty(from_pub):
        s = str(from_pub).strip()
        if strict and not _ISO_DATE_RE.match(s):
            raise ValueError(f"from_publication_date must be YYYY-MM-DD, got: {s!r}")
        out["from_publication_date"] = s
    if not _is_empty(to_pub):
        s = str(to_pub).strip()
        if strict and not _ISO_DATE_RE.match(s):
            raise ValueError(f"to_publication_date must be YYYY-MM-DD, got: {s!r}")
        out["to_publication_date"] = s

    # Venue
    journal = src.pop("journal", None)
    if not _is_empty(journal):
        out["primary_location.source.display_name.search"] = str(journal).strip()

    # Authors
    # - author/authors: author name(s) fuzzy match
    # - author_id/author_ids: OpenAlex author id(s) exact match
    author_ids = src.pop("author_ids", None)
    if _is_empty(author_ids):
        author_ids = src.pop("author_id", None)
    if not _is_empty(author_ids):
        if isinstance(author_ids, (list, tuple)):
            out["authorships.author.id"] = [str(x).strip() for x in author_ids if not _is_empty(x)]
        else:
            out["authorships.author.id"] = str(author_ids).strip()

    authors = src.pop("authors", None)
    if _is_empty(authors):
        authors = src.pop("author", None)
    if not _is_empty(authors):
        # OpenAlex supports `.search` suffix for some fields; here we use display_name.search as a best-effort.
        # NOTE: Union semantics across journal/authors is handled at the caller (tool_service) by multi-request merge.
        if isinstance(authors, (list, tuple)):
            out["authorships.author.display_name.search"] = [str(x).strip() for x in authors if not _is_empty(x)]
        else:
            out["authorships.author.display_name.search"] = str(authors).strip()

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
        key = str(k).strip()
        if strict:
            # Key should be OpenAlex-like field path
            if not re.match(r"^[A-Za-z0-9_.-]+$", key):
                raise ValueError(f"invalid filter key: {key!r}")
            # Only allow scalar or list of scalars
            if isinstance(v, dict):
                raise ValueError(f"invalid filter value type for {key}: dict")
        # Enforce list/scalar size limits (optional; do not hardcode)
        vv = v
        if isinstance(v, (list, tuple)):
            if max_list_len is not None and max_list_len > 0 and len(v) > max_list_len:
                if strict:
                    raise ValueError(f"filter list too long for {key}: {len(v)} > {max_list_len}")
                vv = list(v)[:max_list_len]
            # apply per-item length limit if requested
            if max_value_len is not None and max_value_len > 0:
                trimmed = []
                for item in (vv or []):
                    s = str(item)
                    if len(s) > max_value_len:
                        if strict:
                            raise ValueError(f"filter value too long for {key}: {len(s)} > {max_value_len}")
                        s = s[:max_value_len]
                    trimmed.append(s)
                vv = trimmed
        else:
            if max_value_len is not None and max_value_len > 0:
                s = str(vv)
                if len(s) > max_value_len:
                    if strict:
                        raise ValueError(f"filter value too long for {key}: {len(s)} > {max_value_len}")
                    vv = s[:max_value_len]
        out[key] = vv

    return out

