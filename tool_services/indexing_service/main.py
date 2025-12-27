"""
Indexing Service

职责：
- 接收解析完成产物（doc + chunks），做 embedding（可替换），并写入本地库（SQLite）。
- 提供检索接口（FTS5 关键词检索 + 向量检索 + RRF 融合）。

默认 embedding：hashing embedding（无需外部模型/网络，便于本地跑通）。
"""

import json
import math
import os
import sqlite3
import time
import hashlib
from contextlib import asynccontextmanager
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import chromadb
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    db_path: str = Field("index.db", description="SQLite DB 文件路径")
    embed_dim: int = Field(256, ge=32, le=2048, description="向量维度（hash embedding）")
    chroma_persist_dir: str = Field(
        "chroma_data", description="Chroma 持久化目录（PersistentClient path）"
    )
    chroma_collection: str = Field(
        "paper_chunks", description="Chroma collection 名称"
    )
    chroma_distance: str = Field(
        "cosine", description="Chroma HNSW space（cosine/l2/ip）"
    )

    class Config:
        env_prefix = "INDEX_"
        case_sensitive = False
        extra = "ignore"


settings = Settings()


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(settings.db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS docs (
            doc_id TEXT PRIMARY KEY,
            canonical_id TEXT,
            doc_type TEXT,
            title TEXT,
            authors_json TEXT,
            year INTEGER,
            venue TEXT,
            source TEXT,
            license TEXT,
            open_access INTEGER,
            pdf_object_key TEXT,
            pdf_sha256 TEXT,
            extra_json TEXT,
            created_at_unix INTEGER
        );
        """
    )
    # Backward-compatible schema migration for existing db files.
    for stmt in (
        "ALTER TABLE docs ADD COLUMN doc_type TEXT",
        "ALTER TABLE docs ADD COLUMN extra_json TEXT",
    ):
        try:
            conn.execute(stmt)
        except sqlite3.OperationalError:
            pass
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS chunks (
            chunk_id TEXT PRIMARY KEY,
            doc_id TEXT,
            text TEXT,
            page INTEGER,
            paragraph INTEGER,
            section_path TEXT
        );
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS chunk_vectors (
            chunk_id TEXT PRIMARY KEY,
            dim INTEGER,
            vec BLOB
        );
        """
    )
    # FTS5（若运行环境不支持，会抛错；我们捕获并降级）
    try:
        conn.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts
            USING fts5(chunk_id UNINDEXED, doc_id UNINDEXED, text, section_path);
            """
        )
        conn.execute(
            """
            CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
              INSERT INTO chunks_fts(chunk_id, doc_id, text, section_path)
              VALUES (new.chunk_id, new.doc_id, new.text, new.section_path);
            END;
            """
        )
        conn.execute(
            """
            CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
              DELETE FROM chunks_fts WHERE chunk_id = old.chunk_id;
            END;
            """
        )
    except sqlite3.OperationalError:
        pass
    conn.commit()


def _hash_embed(text: str, dim: int) -> np.ndarray:
    # 简单 hashing embedding：bag-of-words + signed hash
    toks = [t for t in _tokenize(text) if t]
    v = np.zeros((dim,), dtype=np.float32)
    for t in toks:
        h = hash(t)
        idx = h % dim
        sign = 1.0 if (h & 1) == 0 else -1.0
        v[idx] += sign
    # L2 normalize
    n = float(np.linalg.norm(v))
    if n > 0:
        v /= n
    return v


def _sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def _content_hash_from_chunks(chunks: List["ChunkIn"]) -> str:
    # Stable-ish content hash for non-PDF artifacts (dataset/code). Keep it bounded.
    joined = "\n\n".join((c.text or "") for c in chunks)[:2_000_000]
    return _sha256_hex(joined.encode("utf-8", errors="ignore"))


def _tokenize(s: str) -> List[str]:
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


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    # both should already be normalized
    return float(np.dot(a, b))


def _vec_to_blob(v: np.ndarray) -> bytes:
    return v.astype(np.float32).tobytes()


def _blob_to_vec(b: bytes, dim: int) -> np.ndarray:
    v = np.frombuffer(b, dtype=np.float32)
    if v.size != dim:
        # tolerate dimension mismatch by re-normalizing/truncating
        v = v[:dim]
    n = float(np.linalg.norm(v))
    if n > 0:
        v = v / n
    return v.astype(np.float32)


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
    # 对于非 paper（dataset/code），允许不传；服务端会根据 chunks 内容计算一个稳定哈希。
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


import asyncio
from nexus_tool.tool_service import IndexerToolService

@asynccontextmanager
async def lifespan(app: FastAPI):
    conn = _connect()
    _init_db(conn)
    app.state.db = conn

    # Chroma persistent client + collection
    # Align with IndexerToolService defaults
    persist_dir = os.getenv("CHROMA_PERSIST_DIR", ".chroma")
    collection_name = os.getenv("CHROMA_COLLECTION", "morning_report")
    
    os.makedirs(persist_dir, exist_ok=True)
    chroma_client = chromadb.PersistentClient(path=persist_dir)
    # Ensure collection exists with desired metric
    collection = chroma_client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": settings.chroma_distance},
    )
    app.state.chroma_client = chroma_client
    app.state.chroma_collection = collection

    # Start the Worker in background
    print("[Indexing Service] Starting RabbitMQ Worker...")
    service = IndexerToolService()
    worker_task = asyncio.create_task(service.start())

    yield
    
    # Cleanup
    print("[Indexing Service] Stopping RabbitMQ Worker...")
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass
        
    conn.close()


app = FastAPI(
    title="Indexing Service",
    version="0.1.0",
    description="向量化与入库服务（与解析服务解耦）",
    lifespan=lifespan,
)

# 允许前端（不同端口）跨域调用：支持浏览器预检 OPTIONS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
async def health():
    # Basic sanity: make sure collection object exists
    _ = app.state.chroma_collection.name
    return {"status": "ok", "vector_store": "chroma", "collection": app.state.chroma_collection.name}


@app.post("/index", response_model=IndexResponse)
async def index(req: IndexRequest):
    conn: sqlite3.Connection = app.state.db
    collection = app.state.chroma_collection
    doc = req.doc
    if not doc.doc_id:
        raise HTTPException(status_code=400, detail="doc_id 必填")
    if not req.chunks:
        raise HTTPException(status_code=400, detail="chunks 不能为空")

    doc_type = (doc.doc_type or "paper").strip().lower()
    if doc_type not in {"paper", "dataset", "code"}:
        raise HTTPException(status_code=400, detail="doc_type 只支持 paper/dataset/code")
    content_sha256 = (doc.pdf_sha256 or "").strip() or _content_hash_from_chunks(req.chunks)

    # Idempotency: if same pdf_sha256 already indexed for this doc_id, return quickly.
    row = conn.execute("SELECT pdf_sha256 FROM docs WHERE doc_id = ?", (doc.doc_id,)).fetchone()
    if row and (row["pdf_sha256"] or "") == content_sha256:
        return IndexResponse(doc_id=doc.doc_id, chunks_indexed=0, embed_dim=settings.embed_dim)

    authors_json = json.dumps(doc.authors or [], ensure_ascii=False)
    extra_json = json.dumps(doc.extra or {}, ensure_ascii=False)
    created_at = doc.created_at_unix or int(time.time())
    conn.execute(
        """
        INSERT INTO docs(doc_id, canonical_id, doc_type, title, authors_json, year, venue, source, license, open_access, pdf_object_key, pdf_sha256, extra_json, created_at_unix)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(doc_id) DO UPDATE SET
          canonical_id=excluded.canonical_id,
          doc_type=excluded.doc_type,
          title=excluded.title,
          authors_json=excluded.authors_json,
          year=excluded.year,
          venue=excluded.venue,
          source=excluded.source,
          license=excluded.license,
          open_access=excluded.open_access,
          pdf_object_key=excluded.pdf_object_key,
          pdf_sha256=excluded.pdf_sha256,
          extra_json=excluded.extra_json,
          created_at_unix=excluded.created_at_unix
        ;
        """,
        (
            doc.doc_id,
            doc.canonical_id,
            doc_type,
            doc.title,
            authors_json,
            doc.year,
            doc.venue,
            doc.source,
            doc.license,
            None if doc.open_access is None else (1 if doc.open_access else 0),
            doc.pdf_object_key,
            content_sha256,
            extra_json,
            created_at,
        ),
    )

    # Upsert chunks/vectors (simple: delete old for doc then insert fresh)
    if req.upsert:
        old_ids = [r["chunk_id"] for r in conn.execute("SELECT chunk_id FROM chunks WHERE doc_id = ?", (doc.doc_id,))]
        # Delete from Chroma first (ignore if not exist)
        if old_ids:
            try:
                collection.delete(ids=old_ids)
            except Exception:
                pass
        conn.execute("DELETE FROM chunks WHERE doc_id = ?", (doc.doc_id,))

    dim = settings.embed_dim
    count = 0
    chroma_ids: List[str] = []
    chroma_docs: List[str] = []
    chroma_embs: List[List[float]] = []
    chroma_metas: List[Dict[str, Any]] = []
    for ch in req.chunks:
        page = (ch.span or {}).get("page")
        para = (ch.span or {}).get("paragraph")
        conn.execute(
            "INSERT OR REPLACE INTO chunks(chunk_id, doc_id, text, page, paragraph, section_path) VALUES (?, ?, ?, ?, ?, ?)",
            (ch.chunk_id, ch.doc_id, ch.text, page, para, ch.section_path),
        )
        vec = _hash_embed(ch.text, dim=dim)
        chroma_ids.append(ch.chunk_id)
        chroma_docs.append(ch.text)
        chroma_embs.append(vec.astype(np.float32).tolist())
        chroma_metas.append(
            {
                "doc_id": ch.doc_id,
                "canonical_id": doc.canonical_id or "",
                "doc_type": doc_type,
                "title": doc.title or "",
                "page": page if page is not None else -1,
                "paragraph": para if para is not None else -1,
                "section_path": ch.section_path or "",
                "pdf_sha256": content_sha256,
                "pdf_object_key": doc.pdf_object_key or "",
            }
        )
        count += 1

    # Upsert into Chroma in one batch
    try:
        collection.upsert(
            ids=chroma_ids,
            documents=chroma_docs,
            embeddings=chroma_embs,
            metadatas=chroma_metas,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Chroma upsert failed: {e}")

    conn.commit()
    return IndexResponse(doc_id=doc.doc_id, chunks_indexed=count, embed_dim=dim)


def _fts_available(conn: sqlite3.Connection) -> bool:
    try:
        conn.execute("SELECT 1 FROM chunks_fts LIMIT 1")
        return True
    except sqlite3.OperationalError:
        return False


def _search_fts(conn: sqlite3.Connection, query: str, limit: int) -> List[Tuple[str, float]]:
    if not _fts_available(conn):
        return []
    # bm25 越小越好；我们转换成越大越好
    rows = conn.execute(
        "SELECT chunk_id, bm25(chunks_fts) AS bm FROM chunks_fts WHERE chunks_fts MATCH ? ORDER BY bm ASC LIMIT ?",
        (query, limit),
    ).fetchall()
    out = []
    for r in rows:
        bm = float(r["bm"])
        out.append((r["chunk_id"], 1.0 / (1.0 + max(0.0, bm))))
    return out


def _search_vector(conn: sqlite3.Connection, query: str, limit: int) -> List[Tuple[str, float]]:
    # Chroma vector search (embeddings are pre-normalized)
    collection = app.state.chroma_collection
    dim = settings.embed_dim
    qv = _hash_embed(query, dim=dim).astype(np.float32).tolist()
    try:
        res = collection.query(
            query_embeddings=[qv],
            n_results=limit,
            include=["distances", "metadatas", "documents"],
        )
    except Exception:
        return []
    ids = (res.get("ids") or [[]])[0]
    dists = (res.get("distances") or [[]])[0]
    # Chroma distance: cosine distance (smaller better). Convert to similarity.
    out: List[Tuple[str, float]] = []
    for cid, dist in zip(ids, dists):
        try:
            sim = 1.0 - float(dist)
        except Exception:
            sim = 0.0
        out.append((cid, sim))
    return out


def _rrf(ranks: List[List[str]], k: int = 60) -> Dict[str, float]:
    # Reciprocal Rank Fusion: sum 1/(k + rank)
    score: Dict[str, float] = {}
    for lst in ranks:
        for i, cid in enumerate(lst):
            score[cid] = score.get(cid, 0.0) + 1.0 / (k + i + 1)
    return score


@app.post("/search", response_model=SearchResponse)
async def search(req: SearchRequest):
    conn: sqlite3.Connection = app.state.db
    q = req.query.strip()
    if not q:
        raise HTTPException(status_code=400, detail="query 不能为空")

    vec_hits = _search_vector(conn, q, limit=req.k * 3) if req.use_vector else []
    fts_hits = _search_fts(conn, q, limit=req.k * 3) if req.use_fts else []

    vec_rank = [cid for cid, _ in vec_hits]
    fts_rank = [cid for cid, _ in fts_hits]
    fused = _rrf([vec_rank, fts_rank], k=60)

    # Fetch chunk/doc data for top k
    top = sorted(fused.items(), key=lambda x: x[1], reverse=True)[: req.k]
    hits: List[SearchHit] = []
    for cid, rrf_score in top:
        ch = conn.execute(
            "SELECT chunk_id, doc_id, text, page, paragraph, section_path FROM chunks WHERE chunk_id = ?",
            (cid,),
        ).fetchone()
        if not ch:
            continue
        doc = conn.execute(
            "SELECT * FROM docs WHERE doc_id = ?",
            (ch["doc_id"],),
        ).fetchone()
        if not doc:
            continue

        # filter (very small subset)
        if req.kinds:
            allowed = {str(k).lower().strip() for k in req.kinds if str(k).strip()}
            doc_type = ""
            try:
                doc_type = str(doc["doc_type"] or "").lower()
            except Exception:
                doc_type = ""
            if allowed and ((doc_type or "paper") not in allowed):
                continue
        if "canonical_id" in req.filters and req.filters["canonical_id"]:
            if (doc["canonical_id"] or "") != req.filters["canonical_id"]:
                continue

        explain = {
            "rrf": rrf_score,
            "vector": dict(vec_hits).get(cid),
            "fts": dict(fts_hits).get(cid),
        }
        hits.append(
            SearchHit(
                doc=dict(doc),
                chunk=dict(ch),
                score=rrf_score,
                explain=explain,
            )
        )

    return SearchResponse(query=req.query, hits=hits)


@app.get("/kb/overview", response_model=KnowledgeBaseOverviewResponse)
async def kb_overview(limit: int = 20, offset: int = 0):
    """本地知识库概览：论文数量、chunk 数、以及论文列表（按创建时间倒序）。"""
    limit = max(1, min(limit, 200))
    offset = max(0, offset)
    conn: sqlite3.Connection = app.state.db
    docs_count = int(conn.execute("SELECT COUNT(*) AS c FROM docs").fetchone()["c"])
    chunks_count = int(conn.execute("SELECT COUNT(*) AS c FROM chunks").fetchone()["c"])
    rows = conn.execute(
        """
        SELECT doc_id, canonical_id, doc_type, title, year, venue, source, pdf_sha256, created_at_unix
        FROM docs
        ORDER BY created_at_unix DESC
        LIMIT ? OFFSET ?
        """,
        (limit, offset),
    ).fetchall()
    docs = [OverviewDoc(**dict(r)) for r in rows]
    return KnowledgeBaseOverviewResponse(docs_count=docs_count, chunks_count=chunks_count, docs=docs)


