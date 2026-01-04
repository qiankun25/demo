from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.database.session import get_db
from app.models.doc import Doc
from app.models.chunk import Chunk
from app.schemas.api_models import KnowledgeBaseOverviewResponse, OverviewDoc
from app.core.config import settings

router = APIRouter()

@router.get("/kb/overview", response_model=KnowledgeBaseOverviewResponse)
async def kb_overview(
    limit: int = None, 
    offset: int = None, 
    db: Session = Depends(get_db)
):
    if limit is None:
        limit = settings.KB_DEFAULT_LIMIT
    if offset is None:
        offset = settings.KB_DEFAULT_OFFSET
    limit = max(1, min(limit, settings.KB_MAX_LIMIT))
    offset = max(0, offset)
    
    docs_count = db.query(func.count(Doc.doc_id)).scalar()
    chunks_count = db.query(func.count(Chunk.chunk_id)).scalar()
    
    rows = db.query(Doc).order_by(Doc.created_at_unix.desc()).limit(limit).offset(offset).all()
    
    docs = []
    for r in rows:
        docs.append(OverviewDoc(
            doc_id=r.doc_id,
            canonical_id=r.canonical_id,
            doc_type=r.doc_type,
            title=r.title,
            year=r.year,
            venue=r.venue,
            source=r.source,
            pdf_sha256=r.pdf_sha256,
            created_at_unix=r.created_at_unix
        ))
        
    return KnowledgeBaseOverviewResponse(
        docs_count=docs_count,
        chunks_count=chunks_count,
        docs=docs
    )

