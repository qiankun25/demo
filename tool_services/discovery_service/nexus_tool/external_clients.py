"""
外部学术检索客户端（可选能力）

说明：
- 该模块只提供工具函数，不会被 discovery 的现有业务逻辑默认调用；
- 这样可以保证当前 DiscoveryToolService 的输入/输出格式与行为不变。
"""

from __future__ import annotations

import asyncio
import urllib.parse
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional

import httpx

from tool_services.discovery_service.settings import settings


async def search_arxiv(query: str, max_results: int = 5, timeout: float = 15.0) -> List[Dict[str, Any]]:
    """Search arXiv via public Atom API and return basic paper metadata."""
    q = (query or "").strip()
    if not q:
        return []

    base = "https://export.arxiv.org/api/query"
    params = {
        "search_query": f"all:{q}",
        "start": 0,
        "max_results": max_results,
        "sortBy": "relevance",
    }
    url = f"{base}?{urllib.parse.urlencode(params)}"

    headers = {"User-Agent": settings.openalex_user_agent}
    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers=headers) as client:
            resp = await client.get(url)
            resp.raise_for_status()
    except Exception:
        return []

    try:
        root = ET.fromstring(resp.text)
    except Exception:
        return []

    ns = {"atom": "http://www.w3.org/2005/Atom"}
    papers: List[Dict[str, Any]] = []
    for entry in root.findall("atom:entry", ns):
        title_el = entry.find("atom:title", ns)
        summary_el = entry.find("atom:summary", ns)
        link_el = entry.find("atom:id", ns)
        authors = [
            (a.find("atom:name", ns).text or "").strip()
            for a in entry.findall("atom:author", ns)
            if a.find("atom:name", ns) is not None and a.find("atom:name", ns).text
        ]
        papers.append(
            {
                "title": (title_el.text or "").strip() if title_el is not None else "",
                "authors": authors,
                "abstract": (summary_el.text or "").strip() if summary_el is not None else "",
                "url": (link_el.text or "").strip() if link_el is not None else "",
                "source": "arXiv",
            }
        )
    return papers


async def search_semantic_scholar(
    query: str,
    api_key: Optional[str] = None,
    limit: int = 5,
    timeout: float = 15.0,
) -> List[Dict[str, Any]]:
    """Search Semantic Scholar for papers (free tier)."""
    q = (query or "").strip()
    if not q:
        return []

    url = "https://api.semanticscholar.org/graph/v1/paper/search"
    params: Dict[str, Any] = {
        "query": q,
        "limit": limit,
        "fields": "title,authors,year,abstract,url,citationCount",
    }
    headers = {"Accept": "application/json"}
    if api_key:
        headers["x-api-key"] = api_key

    client_headers = {"User-Agent": settings.openalex_user_agent}
    attempts = 0
    backoff = 1.0
    while attempts < 3:
        attempts += 1
        try:
            async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers=client_headers) as client:
                resp = await client.get(url, params=params, headers=headers)
            if resp.status_code == 429:
                await asyncio.sleep(backoff)
                backoff *= 2
                params["limit"] = max(3, int(params["limit"]) // 2)
                continue
            resp.raise_for_status()
            data = resp.json()
            results = data.get("data", []) if isinstance(data, dict) else []
            out: List[Dict[str, Any]] = []
            for r in results:
                if not isinstance(r, dict):
                    continue
                out.append(
                    {
                        "title": r.get("title", ""),
                        "authors": [a.get("name", "") for a in (r.get("authors") or []) if isinstance(a, dict)],
                        "year": r.get("year"),
                        "abstract": r.get("abstract", ""),
                        "citations": r.get("citationCount"),
                        "url": r.get("url", ""),
                        "source": "Semantic Scholar",
                    }
                )
            return out
        except httpx.HTTPStatusError:
            break
        except Exception:
            break
    return []


