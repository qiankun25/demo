from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class DocIn(BaseModel):
    doc_id: str
    canonical_id: Optional[str] = None
    doc_type: Optional[str] = Field(
        default="paper",
        description="资源种类：paper/dataset/code（用于按种类检索与过滤）",
    )
    title: Optional[str] = None
    authors: Optional[List[str]] = None
    year: Optional[int] = None
    venue: Optional[str] = None
    source: Optional[str] = None
    license: Optional[str] = None
    open_access: Optional[bool] = None
    pdf_object_key: Optional[str] = None
    pdf_sha256: Optional[str] = None
    extra: Dict[str, Any] = Field(default_factory=dict)
    created_at_unix: Optional[int] = None

class ChunkIn(BaseModel):
    chunk_id: str
    doc_id: str
    text: str
    span: Optional[Dict[str, int]] = None
    section_path: Optional[str] = None

class SummaryKeywordsIn(BaseModel):
    summary: str = ""
    summary_source: str = ""
    keywords: List[str] = Field(default_factory=list)
    abstract: Optional[str] = None
    abstract_source: Optional[str] = None

class IndexRequest(BaseModel):
    doc: DocIn
    chunks: List[ChunkIn]
    summary_keywords: Optional[SummaryKeywordsIn] = None
    upsert: bool = True

class IndexResponse(BaseModel):
    doc_id: str
    chunks_indexed: int
    embed_dim: int

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    k: int = Field(10, ge=1, le=50)
    kinds: Optional[List[str]] = Field(
        default=None, description="按资源种类过滤：paper/dataset/code；为空则不过滤"
    )
    filters: Dict[str, Any] = Field(default_factory=dict)
    use_vector: bool = True
    use_fts: bool = True

class SearchHit(BaseModel):
    doc: Dict[str, Any]
    chunk: Dict[str, Any]
    score: float
    explain: Dict[str, Any]

class SearchResponse(BaseModel):
    query: str
    hits: List[SearchHit]

class OverviewDoc(BaseModel):
    doc_id: str
    canonical_id: Optional[str] = None
    doc_type: Optional[str] = None
    title: Optional[str] = None
    year: Optional[int] = None
    venue: Optional[str] = None
    source: Optional[str] = None
    pdf_sha256: Optional[str] = None
    created_at_unix: Optional[int] = None

class KnowledgeBaseOverviewResponse(BaseModel):
    docs_count: int
    chunks_count: int
    docs: List[OverviewDoc]

