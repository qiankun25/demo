import json
import time
import hashlib
import numpy as np
import chromadb
from typing import List, Tuple, Dict, Any, Optional
from sqlalchemy.orm import Session
from app.core.config import settings
from app.models.doc import Doc
from app.models.chunk import Chunk
from app.schemas.api_models import IndexRequest, IndexResponse

class IndexerService:
    def __init__(self, chroma_client: chromadb.PersistentClient, collection: chromadb.Collection):
        self.chroma_client = chroma_client
        self.collection = collection

    def _hash_embed(self, text: str, dim: int) -> np.ndarray:
        toks = [t for t in self._tokenize(text) if t]
        v = np.zeros((dim,), dtype=np.float32)
        for t in toks:
            digest = hashlib.sha256(t.encode("utf-8", errors="ignore")).digest()
            h = int.from_bytes(digest[:8], "little", signed=False)
            idx = h % dim
            sign = 1.0 if (h & 1) == 0 else -1.0
            v[idx] += sign
        n = float(np.linalg.norm(v))
        if n > 0:
            v /= n
        return v

    def _tokenize(self, s: str) -> List[str]:
        s = (s or "").lower()
        out = []
        cur = []
        for ch in s:
            if "a" <= ch <= "z" or "0" <= ch <= "9":
                cur.append(ch)
            else:
                if len(cur) >= 3:
                    out.append("".join(cur))
                cur = []
        if len(cur) >= 3:
            out.append("".join(cur))
        return out

    def _content_hash_from_chunks(self, chunks: List[Any]) -> str:
        max_length = settings.CONTENT_HASH_MAX_LENGTH
        joined = "\n\n".join((c.text or "") for c in chunks)[:max_length]
        return hashlib.sha256(joined.encode("utf-8", errors="ignore")).hexdigest()

    async def index_document(self, db: Session, req: IndexRequest) -> IndexResponse:
        doc_in = req.doc
        doc_type = (doc_in.doc_type or "paper").strip().lower()
        content_sha256 = (doc_in.pdf_sha256 or "").strip() or self._content_hash_from_chunks(req.chunks)

        # Check idempotency
        existing_doc = db.query(Doc).filter(Doc.doc_id == doc_in.doc_id).first()
        if existing_doc and existing_doc.pdf_sha256 == content_sha256:
            return IndexResponse(doc_id=doc_in.doc_id, chunks_indexed=0, embed_dim=settings.EMBED_DIM)

        # Upsert doc
        if not existing_doc:
            existing_doc = Doc(doc_id=doc_in.doc_id)
            db.add(existing_doc)
        
        existing_doc.canonical_id = doc_in.canonical_id
        existing_doc.doc_type = doc_type
        existing_doc.title = doc_in.title
        existing_doc.authors_json = json.dumps(doc_in.authors or [], ensure_ascii=False)
        existing_doc.year = doc_in.year
        existing_doc.venue = doc_in.venue
        existing_doc.source = doc_in.source
        existing_doc.license = doc_in.license
        existing_doc.open_access = 1 if doc_in.open_access else 0 if doc_in.open_access is not None else None
        existing_doc.pdf_object_key = doc_in.pdf_object_key
        existing_doc.pdf_sha256 = content_sha256
        existing_doc.extra_json = json.dumps(doc_in.extra or {}, ensure_ascii=False)
        existing_doc.created_at_unix = doc_in.created_at_unix or int(time.time())

        # Delete old chunks if upsert is requested
        if req.upsert:
            old_chunks = db.query(Chunk).filter(Chunk.doc_id == doc_in.doc_id).all()
            old_ids = [c.chunk_id for c in old_chunks]
            if old_ids:
                try:
                    self.collection.delete(ids=old_ids)
                except Exception:
                    pass
                db.query(Chunk).filter(Chunk.doc_id == doc_in.doc_id).delete()

        # Index new chunks
        chroma_ids = []
        chroma_docs = []
        chroma_embs = []
        chroma_metas = []
        
        for ch in req.chunks:
            page = (ch.span or {}).get("page")
            para = (ch.span or {}).get("paragraph")
            
            new_chunk = Chunk(
                chunk_id=ch.chunk_id,
                doc_id=ch.doc_id,
                text=ch.text,
                page=page,
                paragraph=para,
                section_path=ch.section_path
            )
            db.add(new_chunk)
            
            vec = self._hash_embed(ch.text, dim=settings.EMBED_DIM)
            chroma_ids.append(ch.chunk_id)
            chroma_docs.append(ch.text)
            chroma_embs.append(vec.astype(np.float32).tolist())
            chroma_metas.append({
                "doc_id": ch.doc_id,
                "canonical_id": doc_in.canonical_id or "",
                "doc_type": doc_type,
                "title": doc_in.title or "",
                "page": page if page is not None else -1,
                "paragraph": para if para is not None else -1,
                "section_path": ch.section_path or "",
                "pdf_sha256": content_sha256,
                "pdf_object_key": doc_in.pdf_object_key or "",
            })

        # Batch upsert to Chroma
        if chroma_ids:
            self.collection.upsert(
                ids=chroma_ids,
                documents=chroma_docs,
                embeddings=chroma_embs,
                metadatas=chroma_metas
            )

        db.commit()
        return IndexResponse(doc_id=doc_in.doc_id, chunks_indexed=len(req.chunks), embed_dim=settings.EMBED_DIM)

