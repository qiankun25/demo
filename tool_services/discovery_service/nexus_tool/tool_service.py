import os
import sys
import asyncio
import json
import hashlib
import re
from typing import Dict, Any, List, Optional, Tuple


def _repo_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


def _ensure_nexus_sdk_on_path() -> None:
    """
    支持两种目录布局：
    1) 本仓库根目录的 nexus_sdk
    2) 兼容旧路径 orchestration/RabbitMQ/nexus_sdk
    """
    root = _repo_root()
    candidates = [
        os.path.join(root, "nexus_sdk"),
        os.path.join(root, "orchestration", "RabbitMQ", "nexus_sdk"),
    ]
    for c in candidates:
        if os.path.exists(c) and c not in sys.path:
            sys.path.append(c)


_ensure_nexus_sdk_on_path()

from nexus_sdk.base import BaseToolService  # noqa: E402
from nexus_sdk.common import MockStorage  # noqa: E402

from . import config  # noqa: E402
from .filters import encode_filters  # noqa: E402
from .openalex_client import build_works_url, fetch_json_with_retry  # noqa: E402
from .query_enhance import enhance_query  # noqa: E402
from .reducer import reduce_works  # noqa: E402

try:
    # redis-py >= 4.2 provides asyncio client at redis.asyncio
    from redis.asyncio import Redis  # type: ignore
except Exception:  # pragma: no cover
    Redis = None  # type: ignore


class DiscoveryToolService(BaseToolService):
    """
    Discovery ToolService：通过 OpenAlex API 做学术资源发现。

    期望输入 (存储 key 对应的数据结构示例):
    {
        "query": "large language model",
        "filters": {
            // 过滤条件（可选；为空/缺失则不按该条件过滤）
            // --- 时间 ---
            // 最近 N 天（精确到天，会转换成 from_publication_date:YYYY-MM-DD）
            "last_n_days": 30,
            // 或者直接指定日期范围（YYYY-MM-DD）
            "from_date": "2024-01-01",
            "to_date": "2024-12-31",
            // --- 期刊/会议（Venue）---
            // 期刊/会议名模糊匹配（OpenAlex: primary_location.source.display_name.search）
            "journal": "Nature",
            // ISSN 精确匹配（OpenAlex: primary_location.source.issn），可为字符串或列表
            "issn": ["0028-0836"],
            // 也可以直接传 OpenAlex 支持的原生字段（会透传）
            "publication_year": "2023",
            "is_oa": "true"
        },
        "limit": 20,           # 每次最大返回条数（默认 20，<=200）
        "sample": None,        # 可选：使用 OpenAlex sample 参数
        "seed": None           # 可选：sample 的 seed
    }

    输出：
    - output_key: data:discovery:{input_key}
    - 存储内容包含 meta + 截断后的 results
    """

    def __init__(self):
        super().__init__(service_name="discovery", cmd_routing_key="cmd.discovery.start")
        self._redis: Optional["Redis"] = None

    def _cache_enabled(self) -> bool:
        return bool(config.REDIS_URL) and Redis is not None

    async def _get_redis(self) -> Optional["Redis"]:
        if not self._cache_enabled():
            return None
        if self._redis is None:
            # decode_responses=False: keep bytes, we json.loads manually
            self._redis = Redis.from_url(config.REDIS_URL, encoding=None, decode_responses=False)
        return self._redis

    @staticmethod
    def _stable_cache_key(
        *,
        enhanced_query: str,
        filter_str: str,
        per_page: int,
        sample: Any,
        seed: Any,
        select: str,
        mailto: str,
    ) -> str:
        """
        只用“会影响 OpenAlex 请求/输出内容”的字段构造稳定 key。
        注意：不包含 input_key，确保不同任务复用同一缓存结果。
        """
        obj = {
            "openalex_base": config.OPENALEX_BASE,
            "works_path": config.OPENALEX_WORKS_PATH,
            "enhanced_query": enhanced_query,
            "filter": filter_str,
            "per_page": per_page,
            "sample": sample,
            "seed": seed,
            "select": select,
            "mailto": mailto,
        }
        raw = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        digest = hashlib.sha256(raw).hexdigest()
        return f"{config.DISCOVERY_CACHE_PREFIX}:{digest}"

    async def _cache_get(self, cache_key: str) -> Optional[Dict[str, Any]]:
        r = await self._get_redis()
        if r is None:
            return None
        try:
            data = await r.get(cache_key)
            if not data:
                return None
            # redis returns bytes when decode_responses=False
            return json.loads(data.decode("utf-8"))
        except Exception:
            # 缓存失败不影响主流程
            return None

    async def _cache_set(self, cache_key: str, value: Dict[str, Any]) -> None:
        r = await self._get_redis()
        if r is None:
            return
        try:
            payload = json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            ttl = int(getattr(config, "DISCOVERY_CACHE_TTL_S", 3600))
            if ttl and ttl > 0:
                await r.setex(cache_key, ttl, payload)
            else:
                await r.set(cache_key, payload)
        except Exception:
            # 缓存失败不影响主流程
            return

    async def do_work(self, input_key: str, params: dict) -> str:
        payload = await MockStorage.get(input_key)
        if not payload:
            raise ValueError(f"input_key={input_key} not found in storage")

        raw_query = payload.get("query", "")
        _cleaned, enhanced_query = enhance_query(raw_query)
        filters = payload.get("filters", {}) or {}
        limit = int(payload.get("limit", 20))
        limit = max(1, min(limit, int(getattr(config, "DISCOVERY_LIMIT_MAX", 200))))
        sample = payload.get("sample")
        seed = payload.get("seed")

        mailto = self._normalize_mailto(payload.get("mailto") or config.OPENALEX_MAILTO or "")
        select = self._normalize_select(payload.get("select") or config.DEFAULT_SELECT or "")

        strict_filters = bool(
            getattr(config, "DISCOVERY_STRICT_FILTERS", False) or getattr(config, "DISCOVERY_STRICT_VALIDATION", False)
        )

        # Union semantics for journal/authors:
        # OpenAlex filter 语法在不同字段之间基本是 AND，且“期刊名/作者名”的 filter 字段在 OpenAlex 侧不稳定（容易 400）。
        # 因此这里采用“本地 post-filter”的实现：先按其它 filters（年份/is_oa 等）做一次 OpenAlex 请求，
        # 再在返回结果中按 (journal OR author) 做并集过滤。
        filters_src = dict(filters or {})
        journal_raw = filters_src.pop("journal", None)
        authors_raw = None
        author_ids_raw = None
        # support both "author(s)" and "author_id(s)" in user filters
        if "authors" in filters_src or "author" in filters_src:
            authors_raw = filters_src.pop("authors", None)
            if authors_raw is None:
                authors_raw = filters_src.pop("author", None)
        if "author_ids" in filters_src or "author_id" in filters_src:
            author_ids_raw = filters_src.pop("author_ids", None)
            if author_ids_raw is None:
                author_ids_raw = filters_src.pop("author_id", None)

        base_filter_str = encode_filters(
            filters_src,
            strict=strict_filters,
            max_last_n_days=int(getattr(config, "DISCOVERY_MAX_LAST_N_DAYS", 3650)),
            max_keys=int(getattr(config, "DISCOVERY_FILTERS_MAX_KEYS", 0) or 0) or None,
            max_list_len=int(getattr(config, "DISCOVERY_FILTERS_MAX_LIST_LEN", 0) or 0) or None,
            max_value_len=int(getattr(config, "DISCOVERY_FILTERS_MAX_VALUE_LEN", 0) or 0) or None,
        )

        def _as_list(x: Any) -> List[str]:
            if x is None:
                return []
            if isinstance(x, (list, tuple)):
                return [str(i).strip() for i in x if str(i).strip()]
            s = str(x).strip()
            return [s] if s else []

        journal_terms = _as_list(journal_raw)
        author_terms = _as_list(authors_raw)
        # NOTE: author_id(s) 目前不做 post-filter（因为 reduce_works 里没有 author id），后续如需可扩展 select+reducer。
        _author_ids = _as_list(author_ids_raw)

        postfilter_enabled = bool(journal_terms or author_terms)

        # For cache key: include post-filter terms so cached results are correct
        filter_str_for_cache = base_filter_str
        if postfilter_enabled:
            filter_str_for_cache = (
                f"{base_filter_str}::POSTFILTER[journal={','.join(journal_terms)}]"
                f"[author={','.join(author_terms)}]"
            )

        # 1) Redis 缓存命中：直接复用之前的结果（不改变对外输出结构）
        cache_key = self._stable_cache_key(
            enhanced_query=enhanced_query,
            filter_str=filter_str_for_cache,
            per_page=limit,
            sample=sample,
            seed=seed,
            select=select,
            mailto=mailto,
        )
        cached = await self._cache_get(cache_key)
        if isinstance(cached, dict) and cached.get("results") is not None:
            output_key = f"data:discovery:{input_key}"
            await MockStorage.save(output_key, cached)
            return output_key

        sample_i, seed_i = self._normalize_sample_seed(sample, seed)

        request_urls: List[str] = []
        request_metas: List[Dict[str, Any]] = []
        all_results: List[Dict[str, Any]] = []

        async def _fetch_one(filter_str: str, per_page: int) -> Tuple[List[Dict[str, Any]], Any, str, Dict[str, Any]]:
            u = build_works_url(
                search=enhanced_query,
                filter_str=filter_str,
                per_page=per_page,
                sample=sample_i,
                seed=seed_i,
                select=select,
                mailto=mailto,
            )
            d, rm = await fetch_json_with_retry(u)
            rs: List[Dict[str, Any]] = d.get("results", []) if isinstance(d, dict) else []
            m = d.get("meta") if isinstance(d, dict) else None
            return rs, m, u, rm

        metas_seen: List[Any] = []
        # When post-filtering, fetch a bit more to maintain chance of returning `limit` after filtering.
        mult = int(getattr(config, "DISCOVERY_POSTFILTER_MULTIPLIER", 3) or 3)
        fetch_n = limit if not postfilter_enabled else max(limit, min(limit * max(1, mult), int(getattr(config, "DISCOVERY_LIMIT_MAX", 200))))

        rs, m, u, rm = await _fetch_one(base_filter_str, per_page=fetch_n)
        all_results = rs or []
        request_urls = [u]
        request_metas = [rm]
        metas_seen = [m]

        # Dedupe by OpenAlex work id while keeping order (union semantics)
        dedup: List[Dict[str, Any]] = []
        seen_ids = set()
        for w in all_results:
            if not isinstance(w, dict):
                continue
            wid = str(w.get("id") or "")
            key = wid or json.dumps(w, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
            if key in seen_ids:
                continue
            seen_ids.add(key)
            dedup.append(w)
            if len(dedup) >= fetch_n:
                break

        reduced_all = reduce_works(dedup[:fetch_n])

        def _match_journal(w: Dict[str, Any]) -> bool:
            if not journal_terms:
                return False
            # Try best_oa_location.source.display_name -> primary_location.source.display_name
            candidates: List[str] = []
            for loc_key in ("best_oa_location", "primary_location"):
                loc = w.get(loc_key)
                if isinstance(loc, dict):
                    src = loc.get("source")
                    if isinstance(src, dict):
                        dn = str(src.get("display_name") or "").strip()
                        if dn:
                            candidates.append(dn)
            # Fallback: locations[]
            locs = w.get("locations")
            if isinstance(locs, list):
                for loc in locs:
                    if not isinstance(loc, dict):
                        continue
                    src = loc.get("source")
                    if isinstance(src, dict):
                        dn = str(src.get("display_name") or "").strip()
                        if dn:
                            candidates.append(dn)
            cset = {c.lower() for c in candidates if c}
            for t in journal_terms:
                tl = t.lower()
                if any(tl in c for c in cset):
                    return True
            return False

        def _match_author(w: Dict[str, Any]) -> bool:
            if not author_terms:
                return False
            names = w.get("authors") or []
            if not isinstance(names, list):
                return False
            joined = " | ".join(str(n) for n in names if str(n).strip()).lower()
            for t in author_terms:
                if t.lower() in joined:
                    return True
            return False

        if postfilter_enabled:
            # Union: journal OR author
            filtered: List[Dict[str, Any]] = []
            for w in reduced_all:
                if _match_journal(w) or _match_author(w):
                    filtered.append(w)
                if len(filtered) >= limit:
                    break
            reduced = filtered
        else:
            reduced = reduced_all[:limit]

        output_key = f"data:discovery:{input_key}"
        output_value = {
            "query": (raw_query or "").strip(),
            "query_enhanced": enhanced_query,
            "filters": filters,
            "request_url": request_urls[0] if request_urls else "",
            "request_urls": request_urls,
            "request_meta": request_metas[0] if request_metas else {},
            "request_metas": request_metas,
            "meta": metas_seen[0] if metas_seen else None,
            "metas": metas_seen,
            "results": reduced,
        }
        await MockStorage.save(output_key, output_value)
        # 2) 写入 Redis 缓存（失败自动忽略）
        await self._cache_set(cache_key, output_value)
        return output_key

    def _normalize_mailto(self, mailto: Any) -> str:
        m = str(mailto or "").strip()
        if not m:
            return ""
        if m.lower().startswith("mailto:"):
            m = m.split(":", 1)[1].strip()
        # Mailto is case-insensitive; keep canonical lower-case to improve cache hit ratio.
        m = m.lower()
        # Minimal email validation (no hard dependency); strict mode can reject invalid
        if not re.match(r"^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$", m):
            if bool(getattr(config, "DISCOVERY_STRICT_MAILTO", False) or getattr(config, "DISCOVERY_STRICT_VALIDATION", False)):
                raise ValueError(f"invalid mailto: {m!r}")
            return ""
        return m

    def _normalize_select(self, select: Any) -> str:
        s = str(select or "").strip()
        if not s:
            return ""
        max_len = int(getattr(config, "DISCOVERY_SELECT_MAX_LEN", 0) or 0)
        if max_len > 0 and len(s) > max_len:
            if bool(getattr(config, "DISCOVERY_STRICT_SELECT", False) or getattr(config, "DISCOVERY_STRICT_VALIDATION", False)):
                raise ValueError(f"select too long: {len(s)} > {max_len}")
            s = s[:max_len]
        parts = [p.strip() for p in s.split(",")]
        parts = [p for p in parts if p]
        # dedupe keep order
        seen = set()
        out: List[str] = []
        for p in parts:
            # Field name should be OpenAlex-like identifier/path
            if not re.match(r"^[A-Za-z0-9_.-]+$", p):
                if bool(getattr(config, "DISCOVERY_STRICT_SELECT", False) or getattr(config, "DISCOVERY_STRICT_VALIDATION", False)):
                    raise ValueError(f"invalid select field: {p!r}")
                continue
            if p in seen:
                continue
            seen.add(p)
            out.append(p)

        max_fields = int(getattr(config, "DISCOVERY_SELECT_MAX_FIELDS", 0) or 0)
        if max_fields > 0 and len(out) > max_fields:
            if bool(getattr(config, "DISCOVERY_STRICT_SELECT", False) or getattr(config, "DISCOVERY_STRICT_VALIDATION", False)):
                raise ValueError(f"too many select fields: {len(out)} > {max_fields}")
            out = out[:max_fields]

        allowlist_raw = str(getattr(config, "DISCOVERY_SELECT_ALLOWLIST", "") or "").strip()
        if allowlist_raw:
            allow = {x.strip() for x in allowlist_raw.split(",") if x.strip()}
            unknown = [x for x in out if x not in allow]
            if unknown and bool(getattr(config, "DISCOVERY_STRICT_SELECT", False) or getattr(config, "DISCOVERY_STRICT_VALIDATION", False)):
                raise ValueError(f"select contains disallowed fields: {unknown}")
            filtered = [x for x in out if x in allow]
            if not filtered:
                # non-strict: fallback to allowed subset of DEFAULT_SELECT (or empty)
                default_parts = [p.strip() for p in str(getattr(config, "DEFAULT_SELECT", "") or "").split(",") if p.strip()]
                filtered = [p for p in default_parts if p in allow]
            out = filtered

        return ",".join(out)

    def _normalize_sample_seed(self, sample: Any, seed: Any) -> Tuple[Optional[int], Optional[int]]:
        # OpenAlex sample/seed are optional; keep None if missing.
        s_val: Optional[int] = None
        seed_val: Optional[int] = None
        if sample is not None and str(sample).strip() != "":
            try:
                s_val = int(sample)
            except Exception:
                if bool(getattr(config, "DISCOVERY_STRICT_VALIDATION", False)):
                    raise ValueError(f"sample must be int, got: {sample!r}")
                s_val = None
        if seed is not None and str(seed).strip() != "":
            try:
                seed_val = int(seed)
            except Exception:
                if bool(getattr(config, "DISCOVERY_STRICT_VALIDATION", False)):
                    raise ValueError(f"seed must be int, got: {seed!r}")
                seed_val = None
        # If seed provided without sample, OpenAlex may ignore; we keep but can be strict.
        if seed_val is not None and s_val is None and bool(getattr(config, "DISCOVERY_STRICT_VALIDATION", False)):
            raise ValueError("seed provided without sample")
        return s_val, seed_val

if __name__ == "__main__":
    service = DiscoveryToolService()
    try:
        asyncio.run(service.start())
    except KeyboardInterrupt:
        pass
