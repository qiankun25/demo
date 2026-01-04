from __future__ import annotations

from typing import Any, Dict, List, Tuple

from app.clients.indexing_service import search_indexing_service


def _best_effort_paper_view(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Build a stable, user-friendly 'paper' object (best effort).

    Keep keys conservative to avoid breaking callers that expect dict-like data.
    """
    if not isinstance(doc, dict):
        doc = {}
    authors = doc.get("authors")
    if not isinstance(authors, list):
        authors = []
    # Many docs also contain authors_json; we ignore it here.
    return {
        "doc_id": doc.get("doc_id"),
        "canonical_id": doc.get("canonical_id"),
        "doc_type": doc.get("doc_type") or doc.get("kind") or "paper",
        "title": doc.get("title"),
        "authors": authors,
        "year": doc.get("year"),
        "venue": doc.get("venue"),
        "source": doc.get("source"),
        "pdf_sha256": doc.get("pdf_sha256"),
        "pdf_object_key": doc.get("pdf_object_key"),
    }


def _hit_score_from_indexing_hit(hit: Dict[str, Any]) -> Tuple[float, Dict[str, Any]]:
    """Prefer vector similarity (1 - distance) if available, else fallback to rrf score."""
    explain = hit.get("explain") if isinstance(hit.get("explain"), dict) else {}
    score = explain.get("vector")
    try:
        if score is not None:
            return float(score), explain
    except Exception:
        pass
    try:
        return float(hit.get("score") or 0.0), explain
    except Exception:
        return 0.0, explain


async def semantic_search_via_indexing_service(
    *,
    indexing_base_url: str,
    http_timeout: float,
    query: str,
    k: int,
    min_score: float,
) -> Dict[str, Any]:
    """Implement retrieval_service `/semantic_search` by delegating to indexing_service.

    External response structure is preserved by re-shaping indexing_service hits.
    """
    # Import settings to get config values
    from app.config import settings
    
    # Ask indexing_service for vector-only search; we will surface vector score.
    # Request a bit more than k to allow min_score filtering while keeping top-k.
    multiplier = settings.semantic_search_k_multiplier
    max_k = settings.semantic_search_max_k
    raw = await search_indexing_service(
        base_url=indexing_base_url,
        http_timeout=http_timeout,
        query=query,
        k=min(max_k, max(k * multiplier, k)),
        kinds=None,
        filters={},
        use_vector=True,
        use_fts=False,
    )
    hits_in = raw.get("hits") or []
    if not isinstance(hits_in, list):
        hits_in = []

    shaped: List[Dict[str, Any]] = []
    for h in hits_in:
        if not isinstance(h, dict):
            continue
        doc = h.get("doc") if isinstance(h.get("doc"), dict) else {}
        chunk = h.get("chunk") if isinstance(h.get("chunk"), dict) else {}

        score, explain = _hit_score_from_indexing_hit(h)
        if score < float(min_score):
            continue

        chunk_id = str(chunk.get("chunk_id") or "")
        doc_id = str(chunk.get("doc_id") or doc.get("doc_id") or "")
        chunk_text = str(chunk.get("text") or "")

        shaped.append(
            {
                "score": score,
                "chunk_id": chunk_id,
                "doc_id": doc_id,
                "paper": _best_effort_paper_view(doc),
                "chunk_text": chunk_text,
                "chunk": chunk,
                "doc": doc,
                # Old implementation returned Chroma metadatas; we preserve the field with best-effort content.
                "vector_meta": {"explain": explain},
            }
        )

    shaped.sort(key=lambda x: float(x.get("score") or 0.0), reverse=True)
    return {
        "query": query,
        "k": k,
        "hits": shaped[:k],
        "meta": {
            "provider": "indexing_service",
            "indexing_base_url": indexing_base_url,
            "score_source": "explain.vector",
        },
    }


