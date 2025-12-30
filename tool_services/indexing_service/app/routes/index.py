from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.schemas.api_models import IndexRequest, IndexResponse
from app.services.indexer import IndexerService
from fastapi import Request

router = APIRouter()

@router.post("/index", response_model=IndexResponse)
async def index(req: IndexRequest, request: Request, db: Session = Depends(get_db)):
    if not req.doc.doc_id:
        raise HTTPException(status_code=400, detail="doc_id 必填")
    if not req.chunks:
        raise HTTPException(status_code=400, detail="chunks 不能为空")

    indexer = IndexerService(
        chroma_client=request.app.state.chroma_client,
        collection=request.app.state.chroma_collection
    )
    return await indexer.index_document(db, req)

