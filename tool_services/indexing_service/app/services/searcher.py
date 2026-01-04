import json
from typing import List, Tuple, Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
import numpy as np
import chromadb
from app.core.config import settings
from app.models.doc import Doc
from app.models.chunk import Chunk
from app.schemas.api_models import SearchRequest, SearchResponse, SearchHit, SearchHit

class SearcherService:
    def __init__(self, chroma_client: chromadb.PersistentClient, collection: chromadb.Collection):
        self.chroma_client = chroma_client
        self.collection = collection

    def _hash_embed(self, text: str, dim: int) -> np.ndarray:
        # Same as IndexerService, but let's replicate for independence or move to a shared util
        from app.services.indexer import IndexerService
        return IndexerService(None, None)._hash_embed(text, dim)

    def _search_vector(self, query: str, limit: int) -> List[Tuple[str, float]]:
        qv = self._hash_embed(query, dim=settings.EMBED_DIM).astype(np.float32).tolist()
        try:
            res = self.collection.query(
                query_embeddings=[qv],
                n_results=limit,
                include=["distances", "metadatas", "documents"],
            )
        except Exception:
            return []
        
        ids = (res.get("ids") or [[]])[0]
        dists = (res.get("distances") or [[]])[0]
        out = []
        for cid, dist in zip(ids, dists):
            sim = 1.0 - float(dist) if dist is not None else 0.0
            out.append((cid, sim))
        return out

    def _search_fts(self, db: Session, query: str, limit: int) -> List[Tuple[str, float]]:
        # Check if SQLite and if chunks_fts exists
        is_sqlite = db.bind.dialect.name == "sqlite"
        if is_sqlite:
            try:
                # BM25 in SQLite FTS5: lower is better. Convert to higher is better.
                sql = text("SELECT chunk_id, bm25(chunks_fts) AS bm FROM chunks_fts WHERE chunks_fts MATCH :q ORDER BY bm ASC LIMIT :l")
                rows = db.execute(sql, {"q": query, "l": limit}).fetchall()
                return [(r[0], 1.0 / (1.0 + max(0.0, float(r[1])))) for r in rows]
            except Exception:
                return []
        else:
            # PostgreSQL FTS implementation
            try:
                lang = settings.FTS_LANGUAGE
                sql = text(f"""
                    SELECT chunk_id, ts_rank_cd(to_tsvector('{lang}', text), plainto_tsquery('{lang}', :q)) AS rank
                    FROM chunks
                    WHERE to_tsvector('{lang}', text) @@ plainto_tsquery('{lang}', :q)
                    ORDER BY rank DESC LIMIT :l
                """)
                rows = db.execute(sql, {"q": query, "l": limit}).fetchall()
                return [(r[0], float(r[1])) for r in rows]
            except Exception:
                return []

    def _rrf(self, ranks: List[List[str]], k: Optional[int] = None) -> Dict[str, float]:
        if k is None:
            k = settings.RRF_K
        score: Dict[str, float] = {}
        for lst in ranks:
            for i, cid in enumerate(lst):
                score[cid] = score.get(cid, 0.0) + 1.0 / (k + i + 1)
        return score

    async def search(self, db: Session, req: SearchRequest) -> SearchResponse:
        q = req.query.strip()
        multiplier = settings.SEARCH_MULTIPLIER
        vec_hits = self._search_vector(q, limit=req.k * multiplier) if req.use_vector else []
        fts_hits = self._search_fts(db, q, limit=req.k * multiplier) if req.use_fts else []

        vec_rank = [cid for cid, _ in vec_hits]
        fts_rank = [cid for cid, _ in fts_hits]
        fused = self._rrf([vec_rank, fts_rank])

        top = sorted(fused.items(), key=lambda x: x[1], reverse=True)[: req.k]
        hits: List[SearchHit] = []
        
        for cid, rrf_score in top:
            chunk = db.query(Chunk).filter(Chunk.chunk_id == cid).first()
            if not chunk:
                continue
            
            doc = db.query(Doc).filter(Doc.doc_id == chunk.doc_id).first()
            if not doc:
                continue

            # Filtering
            if req.kinds:
                allowed = {str(k).lower().strip() for k in req.kinds if str(k).strip()}
                if allowed and (doc.doc_type not in allowed):
                    continue
            
            if "canonical_id" in req.filters and req.filters["canonical_id"]:
                if doc.canonical_id != req.filters["canonical_id"]:
                    continue

            explain = {
                "rrf": rrf_score,
                "vector": dict(vec_hits).get(cid),
                "fts": dict(fts_hits).get(cid),
            }
            
            # Convert SQLAlchemy models to dict for the response
            doc_dict = {c.name: getattr(doc, c.name) for c in doc.__table__.columns}
            # Special handling for authors_json and extra_json
            if doc_dict.get("authors_json"):
                doc_dict["authors"] = json.loads(doc_dict["authors_json"])
            if doc_dict.get("extra_json"):
                doc_dict["extra"] = json.loads(doc_dict["extra_json"])
            
            chunk_dict = {c.name: getattr(chunk, c.name) for c in chunk.__table__.columns}
            
            hits.append(SearchHit(
                doc=doc_dict,
                chunk=chunk_dict,
                score=rrf_score,
                explain=explain
            ))

        return SearchResponse(query=req.query, hits=hits)

