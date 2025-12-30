from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx


async def search_indexing_service(
    *,
    base_url: str,
    http_timeout: float,
    query: str,
    k: int,
    kinds: Optional[List[str]] = None,
    filters: Optional[Dict[str, Any]] = None,
    use_vector: bool = True,
    use_fts: bool = False,
) -> Dict[str, Any]:
    """Call indexing_service `/search` and return decoded JSON.

    This intentionally keeps a very small contract:
    - If indexing_service errors, raise RuntimeError so caller can map to HTTP 502.
    """
    url = base_url.rstrip("/") + "/search"
    payload: Dict[str, Any] = {
        "query": query,
        "k": k,
        "kinds": kinds,
        "filters": filters or {},
        "use_vector": bool(use_vector),
        "use_fts": bool(use_fts),
    }
    async with httpx.AsyncClient(timeout=http_timeout, trust_env=False) as client:
        resp = await client.post(url, json=payload)
    if resp.status_code >= 400:
        raise RuntimeError(f"indexing_service /search failed: {resp.status_code} {resp.text[:300]!r}")
    try:
        return resp.json()
    except Exception as e:  # pragma: no cover
        raise RuntimeError(f"indexing_service /search invalid json: {e}") from e


