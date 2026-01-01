import os
import sys
import json
import time
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
import httpx

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
        # NOTE: ref-only + migrations mode: DB schema should be created by Alembic job, not at runtime.
        
        # Initialize Chroma
        os.makedirs(settings.CHROMA_PERSIST_DIR, exist_ok=True)
        self.chroma_client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
        self.collection = self.chroma_client.get_or_create_collection(
            name=settings.CHROMA_COLLECTION,
            metadata={"hnsw:space": settings.CHROMA_DISTANCE},
        )
        self.indexer_service = IndexerService(self.chroma_client, self.collection)

    async def do_work(self, input_ref: dict, params: dict) -> tuple[dict, dict]:
        async def _fetch_parsed_via_parser_service(doc_id: str) -> Dict[str, Any]:
            base = os.getenv("INDEX_PARSER_BASE_URL", "http://localhost:8031").rstrip("/")
            url = f"{base}/v1/parsed/{doc_id}"
            async with httpx.AsyncClient(timeout=30.0, trust_env=False) as client:
                r = await client.get(url)
                r.raise_for_status()
                data = r.json()
            if not isinstance(data, dict) or not isinstance(data.get("data"), dict):
                raise ValueError("parser_service returned invalid shape")
            return data["data"]

        if not isinstance(input_ref, dict) or input_ref.get("type") != "parsed_doc" or not input_ref.get("id"):
            raise ValueError("ref-only: cmd.indexer.start requires input_ref.type=parsed_doc with id")
        payload = await _fetch_parsed_via_parser_service(str(input_ref["id"]))

        doc_id = payload.get("doc_id")
        title = payload.get("title")
        fulltext_hash = payload.get("fulltext_hash")
        chunks_data = payload.get("chunks") or []
        
        if not doc_id or not chunks_data:
            raise ValueError("doc_id or chunks missing for indexing")

        # Metadata is provided via params (kept by orchestrator from discovery fan-out).
        paper = (params or {}).get("paper") or {}
        if not isinstance(paper, dict):
            paper = {}
        doc_title = str(paper.get("title") or title or "").strip()
        authors = paper.get("authors") or []
        if not isinstance(authors, list):
            authors = []
        canonical_id = str(paper.get("canonical_id") or paper.get("openalex_id") or paper.get("id") or "").strip()
        pdf_url = str(paper.get("pdf_url") or "").strip()
        doi = str(paper.get("doi") or "").strip()

        year = None
        pub_date = str(paper.get("publication_date") or "").strip()
        if pub_date and len(pub_date) >= 4:
            try:
                year = int(pub_date[:4])
            except:
                pass

        pdf_object_key = ""

        extra = {
            "pdf_url": pdf_url,
            "source_url": pdf_url,
            "doi": doi,
            "publication_date": pub_date,
            "openalex_id": canonical_id,
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

        # Result ref: the doc_id is the stable identifier for indexing outputs
        return (
            {"service": "indexing", "type": "index_record", "id": str(doc_id), "version": "v1"},
            {"chunk_count": len(chunks_in), "collection": settings.CHROMA_COLLECTION},
        )
