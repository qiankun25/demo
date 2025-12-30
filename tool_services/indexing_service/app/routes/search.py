from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.schemas.api_models import SearchRequest, SearchResponse
from app.services.searcher import SearcherService

router = APIRouter()

@router.post("/search", response_model=SearchResponse)
async def search(req: SearchRequest, request: Request, db: Session = Depends(get_db)):
    q = req.query.strip()
    if not q:
        raise HTTPException(status_code=400, detail="query 不能为空")

    searcher = SearcherService(
        chroma_client=request.app.state.chroma_client,
        collection=request.app.state.chroma_collection
    )
    return await searcher.search(db, req)

