import os
import sys
import json
import time
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

def _repo_root() -> str:
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

def _ensure_nexus_sdk_on_path() -> None:
    root = _repo_root()
    candidates = [
        os.path.join(root, "nexus_sdk"),
        os.path.join(root, "orchestration", "RabbitMQ", "nexus_sdk"),
    ]
    for c in candidates:
        if os.path.exists(c) and c not in sys.path:
            sys.path.append(c)

_ensure_nexus_sdk_on_path()

from nexus_sdk.base import BaseToolService
from nexus_sdk.common import MockStorage

# Import app components
# We need to make sure the app directory is in the path or use absolute imports
sys.path.append(os.path.join(_repo_root(), "tool_services", "indexing_service"))

from app.core.config import settings
from app.database.session import SessionLocal, engine, Base
from app.services.indexer import IndexerService
from app.schemas.api_models import IndexRequest, DocIn, ChunkIn
import chromadb

class IndexerToolService(BaseToolService):
    def __init__(self):
        super().__init__(service_name="indexer", cmd_routing_key="cmd.indexer.start")
        # Ensure tables exist
        Base.metadata.create_all(bind=engine)
        
        # Initialize Chroma
        os.makedirs(settings.CHROMA_PERSIST_DIR, exist_ok=True)
        self.chroma_client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
        self.collection = self.chroma_client.get_or_create_collection(
            name=settings.CHROMA_COLLECTION,
            metadata={"hnsw:space": settings.CHROMA_DISTANCE},
        )
        self.indexer_service = IndexerService(self.chroma_client, self.collection)

    async def do_work(self, input_key: str, params: dict) -> str:
        payload = await MockStorage.get(input_key)
        if not payload:
            raise ValueError(f"input_key={input_key} not found in storage")

        doc_id = payload.get("doc_id")
        title = payload.get("title")
        fulltext_hash = payload.get("fulltext_hash")
        chunks_data = payload.get("chunks") or []
        
        if not doc_id or not chunks_data:
            raise ValueError("doc_id or chunks missing for indexing")

        # Build doc info (replicating original logic but cleaner)
        download_key = input_key[len("data:parse:"):] if input_key.startswith("data:parse:") else None
        download_payload = {}
        if download_key:
            dp = await MockStorage.get(download_key)
            if isinstance(dp, dict):
                download_payload = dp

        work = download_payload.get("work", {})
        doc_title = (work.get("title") or title or "").strip()
        authors = work.get("authors") or []

        canonical_id = (work.get("openalex_id") or work.get("id") or "").strip()
        doi = (work.get("doi") or "").strip()
        if not canonical_id and doi:
            canonical_id = f"doi:{doi}"
        
        pdf_url = (download_payload.get("pdf_url") or download_payload.get("source_url") or "").strip()
        if not canonical_id and pdf_url:
            canonical_id = pdf_url

        year = None
        pub_date = (work.get("publication_date") or "").strip()
        if pub_date and len(pub_date) >= 4:
            try:
                year = int(pub_date[:4])
            except:
                pass

        pdf_object_key = (download_payload.get("pdf_storage_key") or download_payload.get("file_path") or "").strip()

        extra = {
            "pdf_url": pdf_url,
            "source_url": (download_payload.get("source_url") or "").strip(),
            "doi": doi,
            "publication_date": pub_date,
            "openalex_id": (work.get("openalex_id") or work.get("id") or "").strip(),
        }

        # Prepare IndexRequest
        doc_in = DocIn(
            doc_id=str(doc_id),
            canonical_id=canonical_id or None,
            doc_type="paper",
            title=doc_title or None,
            authors=[str(a) for a in authors],
            year=year,
            pdf_object_key=pdf_object_key or None,
            pdf_sha256=fulltext_hash or None,
            extra={k: v for k, v in extra.items() if v},
            created_at_unix=int(time.time())
        )

        chunks_in = []
        for c in chunks_data:
            chunks_in.append(ChunkIn(
                chunk_id=str(c.get("chunk_id", "")),
                doc_id=str(doc_id),
                text=str(c.get("text", "")),
                span={"page": c.get("page")} if c.get("page") is not None else None,
                section_path=str(c.get("section_path", ""))
            ))

        req = IndexRequest(doc=doc_in, chunks=chunks_in, upsert=True)

        # Execute indexing using shared service
        db = SessionLocal()
        try:
            await self.indexer_service.index_document(db, req)
        finally:
            db.close()

        output_key = f"data:index:{input_key}"
        await MockStorage.save(
            output_key,
            {
                "doc_id": doc_id,
                "chunk_count": len(chunks_in),
                "vector_count": len(chunks_in),
                "collection": settings.CHROMA_COLLECTION,
                "persist_dir": settings.CHROMA_PERSIST_DIR,
            },
        )
        return output_key
