from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import requests
import asyncio
from config import settings

router = APIRouter(prefix="/api/literature-search", tags=["Literature Search"])

# Configuration
INDEXING_SERVICE_BASE_URL = settings.INDEXING_SERVICE_BASE_URL


class LiteratureSearchRequest(BaseModel):
    """文献检索请求参数"""
    query: str = Field(..., description="检索文本", min_length=1)
    k: int = Field(10, description="返回 top-k 数量", ge=1, le=50)
    kinds: Optional[List[str]] = Field(None, description="按资源种类过滤，可选值：paper / dataset / code")
    filters: Optional[Dict[str, Any]] = Field(default_factory=dict, description="过滤条件")
    use_vector: bool = Field(True, description="是否启用向量检索（语义检索）")
    use_fts: bool = Field(True, description="是否启用关键词检索并融合")


class DocInfo(BaseModel):
    """文档元信息"""
    doc_id: Optional[str] = None
    canonical_id: Optional[str] = None
    doc_type: Optional[str] = None
    title: Optional[str] = None


class ChunkInfo(BaseModel):
    """命中片段信息"""
    chunk_id: Optional[str] = None
    doc_id: Optional[str] = None
    text: Optional[str] = None
    page: Optional[int] = None
    paragraph: Optional[int] = None
    section_path: Optional[str] = None


class ExplainInfo(BaseModel):
    """解释信息"""
    rrf: Optional[float] = None
    vector: Optional[float] = None
    fts: Optional[float] = None


class SearchHit(BaseModel):
    """搜索结果命中项"""
    doc: DocInfo
    chunk: ChunkInfo
    score: float
    explain: Optional[ExplainInfo] = None


class LiteratureSearchResponse(BaseModel):
    """文献检索响应"""
    query: str
    hits: List[SearchHit]


class IndexingServiceClient:
    """Indexing Service 客户端"""
    
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or settings.INDEXING_SERVICE_BASE_URL
        self.session = requests.Session()
        self.session.timeout = 30
    
    def search(self, query: str, k: int = 10, kinds: Optional[List[str]] = None, 
               filters: Optional[Dict[str, Any]] = None, 
               use_vector: bool = True, use_fts: bool = True) -> Dict[str, Any]:
        """执行语义检索/混合检索"""
        url = f"{self.base_url}/search"
        
        payload = {
            "query": query,
            "k": k,
            "filters": filters or {},
            "use_vector": use_vector,
            "use_fts": use_fts
        }
        
        # 如果指定了 kinds，添加到 payload
        if kinds:
            payload["kinds"] = kinds
        
        response = self.session.post(url, json=payload)
        response.raise_for_status()
        return response.json()


def convert_hits_to_results(hits: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    将 Indexing Service 返回的 hits 格式转换为前端期望的 results 格式
    
    Indexing Service 格式：
    {
      "doc": {...},
      "chunk": {...},
      "score": 0.0,
      "explain": {...}
    }
    
    前端期望格式：
    {
      "title": "...",
      "authors": [...],
      "abstract": "...",
      ...
    }
    """
    results = []
    
    for hit in hits:
        doc = hit.get("doc", {})
        chunk = hit.get("chunk", {})
        
        # 构建结果项
        result_item = {
            # 从 doc 中提取基本信息
            "doc_id": doc.get("doc_id"),
            "canonical_id": doc.get("canonical_id"),
            "title": doc.get("title", "无标题"),
            "doc_type": doc.get("doc_type", "paper"),
            
            # 从 chunk 中提取文本内容作为摘要/片段
            "chunk_text": chunk.get("text", ""),
            "chunk_id": chunk.get("chunk_id"),
            "page": chunk.get("page"),
            "paragraph": chunk.get("paragraph"),
            "section_path": chunk.get("section_path"),
            
            # 分数信息
            "score": hit.get("score", 0.0),
            "explain": hit.get("explain", {}),
            
            # 默认字段（如果没有，前端可以处理）
            "authors": [],
            "abstract": chunk.get("text", ""),  # 使用 chunk 文本作为摘要
            "publication_date": None,
            "publication_year": None,
            "doi": None,
            "url": None,
        }
        
        results.append(result_item)
    
    return results


@router.post("", response_model=Dict[str, Any])
async def search_literature(request: LiteratureSearchRequest):
    """
    文献检索
    
    调用 Indexing Service 的 /search API 进行语义检索/混合检索
    根据 API_REFERENCE.md 实现
    """
    client = IndexingServiceClient()
    
    def _search():
        return client.search(
            query=request.query,
            k=request.k,
            kinds=request.kinds,
            filters=request.filters,
            use_vector=request.use_vector,
            use_fts=request.use_fts
        )
    
    try:
        search_response = await asyncio.to_thread(_search)
        
        # 转换格式
        hits = search_response.get("hits", [])
        results = convert_hits_to_results(hits)
        
        # 返回前端期望的格式
        return {
            "query": search_response.get("query", request.query),
            "hits": hits,  # 保留原始 hits 数据
            "results": results,  # 转换为前端格式
            "total": len(results)
        }
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 400:
            error_detail = e.response.json().get("detail", "请求参数错误")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_detail
            )
        elif e.response.status_code in [500, 502]:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Indexing Service 错误: {e.response.text if hasattr(e, 'response') else str(e)}"
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"检索失败: {e.response.text if hasattr(e, 'response') else str(e)}"
            )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"检索失败: {str(e)}"
        )

