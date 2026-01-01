"""
Retrieval Service (Search Orchestrator)

目标：实现你提出的 3 + 5 + 4（部分）：
- 3) 发现服务拆分：对外统一检索编排层（本服务），内部外部连接器仍由 mic_find_url 承担。
- 5) 本地+外部混检：先本地（indexing_service），不足再外部（mic_find_url），外部命中异步入库。
- 4) 事件驱动状态机：PaperDiscovered -> PdfDownloaded -> PdfParsed -> Indexed（SQLite 持久化事件与状态）。

说明：
- 本服务不直接解析/下载/索引，只做编排 + 状态机；实际动作通过调用下游服务完成。
- 幂等：以 doc_key（canonical_id 优先，否则 url hash）作为主键；pdf_sha256 用于去重与状态更新。
"""

import asyncio
import hashlib
import json
import sqlite3
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import httpx
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings

# Ensure nexus_sdk is on path
import sys
import os
root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
candidates = [os.path.join(root, "nexus_sdk"), os.path.join(root, "orchestration", "RabbitMQ", "nexus_sdk")]
for c in candidates:
    if os.path.exists(c) and c not in sys.path:
        sys.path.append(c)

try:
    from nexus_sdk.common import MockStorage
except ImportError:
    MockStorage = None


class Settings(BaseSettings):
    # Upstreams
    discovery_base_url: str = Field("http://localhost:8000", description="mic_find_url")
    download_base_url: str = Field("http://localhost:8001", description="download_service-main")
    parser_base_url: str = Field("http://localhost:3000", description="mico_pdf2json-main")
    indexing_base_url: str = Field("http://localhost:8020", description="indexing_service")

    # Optional credentials for dataset/code ingestion
    kaggle_username: Optional[str] = Field(default=None, description="Kaggle 用户名（用于 view API）")
    kaggle_key: Optional[str] = Field(default=None, description="Kaggle Key（用于 view API）")
    github_token: Optional[str] = Field(default=None, description="GitHub Token（提升 rate limit）")

    # Service
    db_path: str = Field("retrieval.db", description="SQLite 文件")
    http_timeout: float = Field(30.0, gt=0)

    # Retrieval strategy
    local_first: bool = Field(True, description="是否优先本地检索")
    min_local_hits: int = Field(5, ge=0, description="本地命中不足则触发外部检索")
    min_local_score: float = Field(
        0.01,
        ge=0.0,
        description="本地命中计数的相似度阈值（仅 score >= 阈值的 hit 才计入 min_local_hits/k 判定）",
    )
    ingest_external_hits: bool = Field(True, description="是否将外部命中异步入库")

    # Download polling (for worker pipeline)
    download_poll_interval: float = Field(5.0, gt=0)
    download_max_polls: int = Field(60, ge=1)

    # Worker
    worker_enabled: bool = Field(True)
    worker_poll_interval: float = Field(1.0, gt=0)
    max_event_attempts: int = Field(5, ge=1, le=20)

    # Local vector+metadata DB (written by IndexerToolService / indexing_service)
    # NOTE: This is a local file-based integration. In docker deployment, you must mount the same volumes.
    index_db_path: str = Field(
        default_factory=lambda: os.getenv("RETRIEVAL_INDEX_DB_PATH")
        or os.getenv("INDEX_DB_PATH")
        or os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "indexing_service", "index.db")),
        description="Indexing SQLite 路径（docs/chunks）。默认指向 ../indexing_service/index.db",
    )
    chroma_persist_dir: str = Field(
        default_factory=lambda: os.getenv("RETRIEVAL_CHROMA_PERSIST_DIR")
        or os.getenv("INDEX_CHROMA_PERSIST_DIR")
        or os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "indexing_service", "chroma_data")),
        description="Chroma 持久化目录。默认指向 ../indexing_service/chroma_data",
    )
    chroma_collection: str = Field(
        default_factory=lambda: os.getenv("RETRIEVAL_CHROMA_COLLECTION")
        or os.getenv("INDEX_CHROMA_COLLECTION")
        or "paper_chunks",
        description="Chroma collection 名称（需与 IndexerToolService 一致）",
    )
    chroma_distance: str = Field(
        default_factory=lambda: os.getenv("RETRIEVAL_CHROMA_DISTANCE")
        or os.getenv("INDEX_CHROMA_DISTANCE")
        or "cosine",
        description="Chroma 距离度量（cosine/l2/ip；用于 score 解释）",
    )
    embed_dim: int = Field(
        default_factory=lambda: int(os.getenv("RETRIEVAL_EMBED_DIM") or os.getenv("INDEX_EMBED_DIM") or "256"),
        ge=32,
        le=2048,
        description="Hash embedding 维度（需与 IndexerToolService 一致）",
    )

    class Config:
        env_prefix = "RETRIEVAL_"
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
        CREATE TABLE IF NOT EXISTS doc_state (
          doc_key TEXT PRIMARY KEY,
          canonical_id TEXT,
          source TEXT,
          source_url TEXT,
          title TEXT,
          authors_json TEXT,
          year INTEGER,
          venue TEXT,
          status TEXT,
          pdf_sha256 TEXT,
          pdf_object_key TEXT,
          last_error TEXT,
          updated_at_unix INTEGER
        );
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
          event_id TEXT PRIMARY KEY,
          event_type TEXT,
          doc_key TEXT,
          payload_json TEXT,
          status TEXT,
          attempts INTEGER,
          next_run_at_unix INTEGER,
          created_at_unix INTEGER
        );
        """
    )
    conn.execute("CREATE INDEX IF NOT EXISTS idx_events_due ON events(status, next_run_at_unix);")
    conn.commit()


def _now() -> int:
    return int(time.time())


def _new_id() -> str:
    raw = f"{time.time_ns()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:24]


def _doc_key(canonical_id: Optional[str], url: str) -> str:
    base = canonical_id.strip() if canonical_id else ""
    if base:
        return "cid:" + base
    return "url:" + hashlib.sha256(url.encode()).hexdigest()[:32]


def _join(base: str, path: str) -> str:
    return base.rstrip("/") + "/" + path.lstrip("/")


def _is_probable_pdf_url(url: str) -> bool:
    u = (url or "").lower()
    return u.endswith(".pdf") or "arxiv.org/pdf/" in u


# --------- Models ---------
class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1)
    k: int = Field(10, ge=1, le=50)
    kinds: Optional[List[str]] = Field(
        default=None, description="查询种类：paper/dataset/code；为空则每类各取 1 个（若可用）"
    )
    filters: Dict[str, Any] = Field(default_factory=dict)
    sources: Optional[List[str]] = None


class SearchSimpleRequest(BaseModel):
    query: str = Field(..., min_length=1)
    top_k: int = Field(5, ge=1, le=50)


class SearchResponse(BaseModel):
    query: str
    local_hits: List[Dict[str, Any]]
    external_hits: List[Dict[str, Any]]
    merged_hits: List[Dict[str, Any]]
    ingest_enqueued: int


class StatusResponse(BaseModel):
    doc_key: str
    status: str
    canonical_id: Optional[str] = None
    pdf_sha256: Optional[str] = None
    last_error: Optional[str] = None


class KnowledgeBaseOverviewDoc(BaseModel):
    doc_id: str
    canonical_id: Optional[str] = None
    title: Optional[str] = None
    year: Optional[int] = None
    venue: Optional[str] = None
    source: Optional[str] = None
    pdf_sha256: Optional[str] = None
    created_at_unix: Optional[int] = None


class KnowledgeBaseOverviewResponse(BaseModel):
    docs_count: int
    chunks_count: int
    docs: List[KnowledgeBaseOverviewDoc]


class SemanticSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="语义检索 query")
    k: int = Field(10, ge=1, le=50, description="返回命中数量")
    min_score: float = Field(0.0, ge=-1.0, le=1.0, description="最小 score（粗过滤；cosine 下通常 1-dist）")


class SemanticSearchHit(BaseModel):
    score: float
    chunk_id: str
    doc_id: str
    paper: Dict[str, Any]
    chunk_text: str
    chunk: Dict[str, Any]
    doc: Dict[str, Any]
    vector_meta: Dict[str, Any]


class SemanticSearchResponse(BaseModel):
    query: str
    k: int
    hits: List[SemanticSearchHit]
    meta: Dict[str, Any]


@dataclass
class Event:
    event_id: str
    event_type: str
    doc_key: str
    payload: Dict[str, Any]
    attempts: int


# --------- App + worker ---------
@asynccontextmanager
async def lifespan(app: FastAPI):
    conn = _connect()
    _init_db(conn)
    app.state.db = conn

    stop = asyncio.Event()
    app.state._stop = stop
    if settings.worker_enabled:
        task = asyncio.create_task(_worker_loop(app, stop))
        app.state._worker_task = task
    yield
    stop.set()
    if getattr(app.state, "_worker_task", None):
        try:
            await app.state._worker_task
        except Exception:
            pass
    conn.close()


app = FastAPI(
    title="Retrieval Service",
    version="0.1.0",
    description="统一检索编排层 + 事件驱动入库状态机",
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
    ready = await health_ready()
    code = ready.status_code
    payload = ready.body
    try:
        shaped = json.loads(payload.decode("utf-8"))
    except Exception:
        shaped = {"status": "unknown", "raw": str(payload)}
    shaped.setdefault("service", "retrieval_service")
    shaped.setdefault("timestamp", time.time())
    return JSONResponse(status_code=code, content=shaped)


@app.get("/health/live")
async def health_live():
    return {"status": "alive"}


@app.get("/health/ready")
async def health_ready():
    components: Dict[str, Any] = {}
    ok = True

    # Local state DB (SQLite)
    try:
        conn: sqlite3.Connection = app.state.db
        conn.execute("SELECT 1").fetchone()
        components["state_db"] = "ok"
    except Exception as e:
        ok = False
        components["state_db"] = f"error: {e}"

    # Downstream: indexing_service (required for semantic search / kb overview)
    try:
        base = (settings.indexing_base_url or "").rstrip("/")
        if not base:
            raise RuntimeError("RETRIEVAL_INDEXING_BASE_URL not configured")
        async with httpx.AsyncClient(timeout=min(settings.http_timeout, 5.0), trust_env=False) as client:
            # prefer readiness if available
            url = _join(base, "/health/ready")
            r = await client.get(url)
            if r.status_code >= 400:
                # fallback to /health
                r = await client.get(_join(base, "/health"))
            if r.status_code >= 400:
                raise RuntimeError(f"indexing_service unhealthy: {r.status_code} {r.text[:200]!r}")
        components["indexing_service"] = "ok"
    except Exception as e:
        ok = False
        components["indexing_service"] = f"error: {e}"

    status_code = status.HTTP_200_OK if ok else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(status_code=status_code, content={"status": "ready" if ok else "not ready", "components": components})


@app.get("/status/{doc_key}", response_model=StatusResponse)
async def status(doc_key: str):
    conn: sqlite3.Connection = app.state.db
    row = conn.execute("SELECT * FROM doc_state WHERE doc_key = ?", (doc_key,)).fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="not found")
    return StatusResponse(
        doc_key=row["doc_key"],
        status=row["status"] or "UNKNOWN",
        canonical_id=row["canonical_id"],
        pdf_sha256=row["pdf_sha256"],
        last_error=row["last_error"],
    )


@app.get("/kb/overview", response_model=KnowledgeBaseOverviewResponse)
async def kb_overview(limit: int = 20, offset: int = 0):
    """查询当前本地知识库概述信息（论文数量、论文标题等）。

    本服务不直接访问 indexing_service 的底层数据库，而是调用 indexing_service 的只读接口 `/kb/overview`。
    """
    url = _join(settings.indexing_base_url, "/kb/overview")
    params = {"limit": max(1, min(limit, 200)), "offset": max(0, offset)}
    async with httpx.AsyncClient(timeout=settings.http_timeout, trust_env=False) as client:
        resp = await client.get(url, params=params)
        if resp.status_code >= 400:
            raise HTTPException(status_code=502, detail=f"indexing_service /kb/overview 失败: {resp.status_code} {resp.text[:300]!r}")
        data = resp.json()
    return KnowledgeBaseOverviewResponse(**data)


def _connect_index_db() -> sqlite3.Connection:
    """Connect to indexing SQLite (docs/chunks) written by IndexerToolService."""
    conn = sqlite3.connect(settings.index_db_path, timeout=30.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def _tokenize(s: str) -> List[str]:
    s = (s or "").lower()
    out: List[str] = []
    cur: List[str] = []
    for ch in s:
        if ("a" <= ch <= "z") or ("0" <= ch <= "9"):
            cur.append(ch)
        else:
            if len(cur) >= 3:
                out.append("".join(cur))
            cur = []
    if len(cur) >= 3:
        out.append("".join(cur))
    return out


def _hash_embed(text: str, dim: int) -> List[float]:
    """Hashing embedding: must match IndexerToolService implementation."""
    try:
        import numpy as np  # noqa: WPS433
    except Exception as e:
        raise RuntimeError("numpy is required for semantic_search. Please pip install -r requirements.txt") from e
    toks = _tokenize(text)
    v = np.zeros((dim,), dtype=np.float32)
    for t in toks:
        # NOTE: 不要使用 Python 内建 hash()（默认有随机盐，跨进程不稳定）
        digest = hashlib.sha256(t.encode("utf-8", errors="ignore")).digest()
        h = int.from_bytes(digest[:8], "little", signed=False)
        idx = h % dim
        sign = 1.0 if (h & 1) == 0 else -1.0
        v[idx] += sign
    n = float(np.linalg.norm(v))
    if n > 0:
        v /= n
    return v.astype(np.float32).tolist()


def _score_from_distance(dist: Any, distance_kind: str) -> float:
    """Convert Chroma returned distance to a 'higher is better' score."""
    try:
        d = float(dist)
    except Exception:
        d = 0.0
    dk = (distance_kind or "cosine").lower().strip()
    if dk == "ip":
        # Inner product: larger is better already (Chroma may return negative/positive).
        return d
    # cosine/l2: smaller is better -> convert to similarity-like score
    return 1.0 - d


@app.post("/semantic_search", response_model=SemanticSearchResponse)
async def semantic_search(req: SemanticSearchRequest):
    """
    语义检索（统一走 indexing_service 的 API）：
    - 本服务不再直连 Chroma/index.db，避免多实例部署下的读一致性问题
    - 保持对外响应结构不变（SemanticSearchResponse）
    """
    q = (req.query or "").strip()
    if not q:
        raise HTTPException(status_code=400, detail="query 不能为空")

    # Important: use local package import so `uvicorn main:app` works even when
    # repo root is not on PYTHONPATH (common in local dev).
    from app.services.semantic_search import semantic_search_via_indexing_service

    try:
        shaped = await semantic_search_via_indexing_service(
            indexing_base_url=settings.indexing_base_url,
            http_timeout=settings.http_timeout,
            query=q,
            k=req.k,
            min_score=req.min_score,
        )
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"semantic_search via indexing_service failed: {e}") from e

    hits: List[SemanticSearchHit] = []
    for h in (shaped.get("hits") or []):
        if not isinstance(h, dict):
            continue
        try:
            hits.append(SemanticSearchHit(**h))
        except Exception:
            continue

    return SemanticSearchResponse(
        query=shaped.get("query") or req.query,
        k=int(shaped.get("k") or req.k),
        hits=hits,
        meta=shaped.get("meta") or {},
    )


@app.post("/search", response_model=SearchResponse)
async def search(req: SearchRequest):
    q = req.query.strip()
    k = req.k

    local_hits: List[Dict[str, Any]] = []
    external_hits: List[Dict[str, Any]] = []
    ingest_cnt = 0

    # 1) local search
    if settings.local_first:
        local_hits = await _search_local(q, k=k, filters=req.filters, kinds=req.kinds)

    # Count only "high-similarity" local hits for deciding whether to do external supplementation.
    qualified_local = []
    for h in local_hits:
        try:
            score = float(h.get("score") or 0.0)
        except Exception:
            score = 0.0
        if score >= settings.min_local_score:
            qualified_local.append(h)
    # Also filter what we return to users: only keep qualified local hits.
    # If you want to inspect all raw local hits for debugging, lower the threshold or add a separate debug endpoint.
    local_hits = qualified_local

    # 2) external search if needed
    if len(qualified_local) < max(settings.min_local_hits, k):
        external_hits = await _search_external(
            q, sources=req.sources, limit=min(10, k), kinds=req.kinds
        )
        if settings.ingest_external_hits:
            ingest_cnt = _enqueue_ingest(external_hits)

    merged = _merge_hits(local_hits, external_hits, k=k)
    return SearchResponse(
        query=req.query,
        local_hits=local_hits,
        external_hits=external_hits,
        merged_hits=merged,
        ingest_enqueued=ingest_cnt,
    )

@app.post("/search_simple")
async def search_simple(req: SearchSimpleRequest):
    """Standalone local search that doesn't depend on indexing_service.
    It scans MockStorage (MinIO) 'data:parse:' entries for keyword matches.
    """
    if MockStorage is None:
        raise HTTPException(status_code=500, detail="nexus_sdk.common.MockStorage not available")
    
    query = req.query.strip()
    top_k = req.top_k
    
    hits: List[Tuple[float, Dict[str, Any]]] = []
    # Use environment or default limit
    scan_limit = int(os.getenv("RETRIEVAL_LOCAL_SCAN_LIMIT", "50"))
    
    try:
        keys = await MockStorage.list_keys("data:parse:")
        for k in keys[:scan_limit]:
            v = await MockStorage.get(k)
            if not isinstance(v, dict):
                continue
            chunks = v.get("chunks") or []
            for c in chunks:
                if not isinstance(c, dict):
                    continue
                text = c.get("text", "")
                # Simple scoring: overlap ratio
                score = 0.0
                if query and text:
                    q_tokens = set(query.lower().split())
                    t_tokens = text.lower().split()
                    if t_tokens:
                        overlap = len(q_tokens.intersection(t_tokens))
                        score = overlap / len(q_tokens) if q_tokens else 0.0
                
                if score > 0:
                    hits.append((score, {
                        "chunk_id": c.get("chunk_id"),
                        "doc_id": v.get("doc_id"),
                        "text": text,
                        "score": score,
                        "source": "local_simple",
                    }))
        
        hits.sort(key=lambda x: x[0], reverse=True)
        return {
            "query": query,
            "hits": [h[1] for h in hits[:top_k]]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Simple search failed: {str(e)}")


async def _search_local(
    query: str, k: int, filters: Dict[str, Any], kinds: Optional[List[str]]
) -> List[Dict[str, Any]]:
    url = _join(settings.indexing_base_url, "/search")
    payload = {
        "query": query,
        "k": k,
        "kinds": kinds,
        "filters": filters,
        "use_vector": True,
        "use_fts": True,
    }
    async with httpx.AsyncClient(timeout=settings.http_timeout, trust_env=False) as client:
        resp = await client.post(url, json=payload)
        if resp.status_code >= 400:
            return []
        data = resp.json()
        hits = data.get("hits") or []
        # normalize
        out = []
        for h in hits:
            out.append(
                {
                    "kind": "local",
                    "score": h.get("score"),
                    "doc": h.get("doc"),
                    "chunk": h.get("chunk"),
                    "explain": h.get("explain"),
                }
            )
        return out


async def _search_external(
    query: str, sources: Optional[List[str]], limit: int, kinds: Optional[List[str]]
) -> List[Dict[str, Any]]:
    url = _join(settings.discovery_base_url, "/search")
    payload: Dict[str, Any] = {
        "query": query,
        "limit": limit,
        "user_id": "retrieval_service",
        "kinds": kinds,
    }
    if sources:
        payload["sources"] = sources
    async with httpx.AsyncClient(timeout=settings.http_timeout, trust_env=False) as client:
        resp = await client.post(url, json=payload)
        if resp.status_code >= 400:
            return []
        data = resp.json()
        resources = data.get("resources") or []
        out = []
        for r in resources:
            out.append({"kind": "external", "resource": r})
        return out


def _merge_hits(local_hits: List[Dict[str, Any]], external_hits: List[Dict[str, Any]], k: int) -> List[Dict[str, Any]]:
    # very simple: local first then external, dedup by canonical_id/url/title
    seen = set()
    out = []
    for h in local_hits:
        doc = h.get("doc") or {}
        cid = doc.get("canonical_id") or ""
        key = ("cid:" + cid) if cid else ("doc:" + (doc.get("doc_id") or ""))
        if key not in seen:
            seen.add(key)
            out.append(h)
        if len(out) >= k:
            return out
    for h in external_hits:
        r = h.get("resource") or {}
        key = (r.get("url") or "") + "|" + (r.get("title") or "")
        if key and key not in seen:
            seen.add(key)
            out.append(h)
        if len(out) >= k:
            break
    return out


def _enqueue_ingest(external_hits: List[Dict[str, Any]]) -> int:
    conn: sqlite3.Connection = app.state.db
    cnt = 0
    for h in external_hits:
        r = h.get("resource") or {}
        url = (r.get("url") or "").strip()
        rtype = (r.get("resource_type") or "paper").lower().strip()
        canonical_id = _infer_canonical_id(r)
        dkey = _doc_key(canonical_id, url or canonical_id or r.get("title") or "")
        # upsert doc_state
        row = conn.execute("SELECT status FROM doc_state WHERE doc_key = ?", (dkey,)).fetchone()
        if row and (row["status"] in {"DOWNLOADED", "PARSED", "INDEXED"}):
            continue
        conn.execute(
            """
            INSERT INTO doc_state(doc_key, canonical_id, source, source_url, title, authors_json, year, venue, status, updated_at_unix)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(doc_key) DO UPDATE SET
              canonical_id=excluded.canonical_id,
              source=excluded.source,
              source_url=excluded.source_url,
              title=excluded.title,
              authors_json=excluded.authors_json,
              year=excluded.year,
              venue=excluded.venue,
              status=COALESCE(doc_state.status, excluded.status),
              updated_at_unix=excluded.updated_at_unix
            ;
            """,
            (
                dkey,
                canonical_id,
                r.get("source") or "",
                url,
                r.get("title") or "",
                json.dumps([], ensure_ascii=False),
                None,
                "",
                "DISCOVERED",
                _now(),
            ),
        )
        # enqueue event by type
        event_type = (
            "PaperDiscovered"
            if rtype == "paper"
            else ("DatasetDiscovered" if rtype == "dataset" else ("CodeDiscovered" if rtype == "code" else ""))
        )
        if not event_type:
            continue
        if not conn.execute(
            "SELECT 1 FROM events WHERE doc_key = ? AND event_type = ? AND status IN ('PENDING','RUNNING')",
            (dkey, event_type),
        ).fetchone():
            ev = {
                "resource_type": rtype,
                "canonical_id": canonical_id,
                "source": r.get("source") or "",
                "url": url,
                "title": r.get("title") or "",
                "description": r.get("description") or "",
                "extra": r.get("extra") or {},
            }
            conn.execute(
                "INSERT INTO events(event_id, event_type, doc_key, payload_json, status, attempts, next_run_at_unix, created_at_unix) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (_new_id(), event_type, dkey, json.dumps(ev, ensure_ascii=False), "PENDING", 0, _now(), _now()),
            )
            cnt += 1
    conn.commit()
    return cnt


def _infer_canonical_id(resource: Dict[str, Any]) -> str:
    # if url looks like arxiv pdf
    url = resource.get("url") or ""
    import re

    m = re.search(r"/pdf/(\d{4}\.\d{4,5})", url)
    if m:
        return "arxiv:" + m.group(1)
    # kaggle
    extra = resource.get("extra") or {}
    ref = (extra.get("ref") or "").strip()
    if ref:
        return "kaggle:" + ref
    # github
    full_name = (extra.get("full_name") or "").strip()
    if full_name:
        return "github:" + full_name
    return ""


async def _worker_loop(app: FastAPI, stop: asyncio.Event) -> None:
    while not stop.is_set():
        try:
            ev = _pick_due_event(app.state.db)
            if not ev:
                await asyncio.sleep(settings.worker_poll_interval)
                continue
            await _handle_event(app, ev)
        except Exception:
            await asyncio.sleep(1.0)


def _pick_due_event(conn: sqlite3.Connection) -> Optional[Event]:
    now = _now()
    row = conn.execute(
        """
        SELECT * FROM events
        WHERE status = 'PENDING' AND next_run_at_unix <= ?
        ORDER BY created_at_unix ASC
        LIMIT 1
        """,
        (now,),
    ).fetchone()
    if not row:
        return None
    conn.execute("UPDATE events SET status='RUNNING' WHERE event_id = ?", (row["event_id"],))
    conn.commit()
    return Event(
        event_id=row["event_id"],
        event_type=row["event_type"],
        doc_key=row["doc_key"],
        payload=json.loads(row["payload_json"] or "{}"),
        attempts=int(row["attempts"] or 0),
    )


async def _handle_event(app: FastAPI, ev: Event) -> None:
    try:
        if ev.event_type == "PaperDiscovered":
            await _transition_download(app, ev)
        elif ev.event_type == "DatasetDiscovered":
            await _transition_dataset_index(app, ev)
        elif ev.event_type == "CodeDiscovered":
            await _transition_code_index(app, ev)
        elif ev.event_type == "PdfDownloaded":
            await _transition_parse(app, ev)
        elif ev.event_type == "PdfParsed":
            await _transition_index(app, ev)
        elif ev.event_type == "Indexed":
            _mark_event_done(app.state.db, ev.event_id)
        else:
            _fail_event(app.state.db, ev, f"unknown event_type={ev.event_type}")
    except Exception as e:
        _retry_or_fail(app.state.db, ev, str(e))


def _retry_or_fail(conn: sqlite3.Connection, ev: Event, err: str) -> None:
    attempts = ev.attempts + 1
    if attempts >= settings.max_event_attempts:
        _fail_event(conn, ev, err)
        return
    delay = min(60, 2 ** attempts)
    conn.execute(
        "UPDATE events SET status='PENDING', attempts=?, next_run_at_unix=? WHERE event_id=?",
        (attempts, _now() + delay, ev.event_id),
    )
    conn.execute(
        "UPDATE doc_state SET last_error=?, updated_at_unix=? WHERE doc_key=?",
        (err, _now(), ev.doc_key),
    )
    conn.commit()


def _mark_event_done(conn: sqlite3.Connection, event_id: str) -> None:
    conn.execute("UPDATE events SET status='DONE' WHERE event_id=?", (event_id,))
    conn.commit()


def _fail_event(conn: sqlite3.Connection, ev: Event, err: str) -> None:
    conn.execute("UPDATE events SET status='FAILED', attempts=? WHERE event_id=?", (ev.attempts + 1, ev.event_id))
    conn.execute(
        "UPDATE doc_state SET status='FAILED', last_error=?, updated_at_unix=? WHERE doc_key=?",
        (err, _now(), ev.doc_key),
    )
    conn.commit()


async def _transition_download(app: FastAPI, ev: Event) -> None:
    # DISCOVERED -> DOWNLOADED (download_service)
    conn: sqlite3.Connection = app.state.db
    url = ev.payload.get("url") or ""
    if not url:
        raise RuntimeError("missing url in PaperDiscovered")
    # create task
    async with httpx.AsyncClient(timeout=settings.http_timeout, trust_env=False) as client:
        resp = await client.post(_join(settings.download_base_url, "/download"), json={"url": url})
        if resp.status_code >= 400:
            raise RuntimeError(f"download create failed: {resp.status_code} {resp.text}")
        task_id = resp.json().get("task_id")
        if not task_id:
            raise RuntimeError("download task_id missing")
        # poll
        file_url = ""
        for _ in range(settings.download_max_polls):
            st = await client.get(_join(settings.download_base_url, f"/download/{task_id}"))
            data = st.json()
            if data.get("status") in {"success", "completed"} and data.get("file_url"):
                file_url = data["file_url"]
                break
            if data.get("status") == "failed":
                raise RuntimeError(f"download failed: {data.get('error_message')}")
            await asyncio.sleep(settings.download_poll_interval)
        if not file_url:
            raise RuntimeError("download timeout")

    conn.execute("UPDATE doc_state SET status='DOWNLOADED', updated_at_unix=? WHERE doc_key=?", (_now(), ev.doc_key))
    # enqueue PdfDownloaded
    payload = {**ev.payload, "file_url": file_url}
    conn.execute(
        "INSERT INTO events(event_id, event_type, doc_key, payload_json, status, attempts, next_run_at_unix, created_at_unix) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (_new_id(), "PdfDownloaded", ev.doc_key, json.dumps(payload, ensure_ascii=False), "PENDING", 0, _now(), _now()),
    )
    _mark_event_done(conn, ev.event_id)


async def _transition_parse(app: FastAPI, ev: Event) -> None:
    # DOWNLOADED -> PARSED
    conn: sqlite3.Connection = app.state.db
    file_url = ev.payload.get("file_url") or ""
    if not file_url:
        raise RuntimeError("missing file_url")
    # fetch pdf bytes
    async with httpx.AsyncClient(timeout=settings.http_timeout, trust_env=False) as client:
        pdf_resp = await client.get(file_url)
        if pdf_resp.status_code >= 400:
            raise RuntimeError(f"fetch pdf failed: {pdf_resp.status_code} {pdf_resp.text[:200]!r}")
        pdf_bytes = pdf_resp.content

        # pass meta into parser; doc_id stable derived from doc_key
        doc_id = hashlib.sha256(ev.doc_key.encode()).hexdigest()[:32]
        data = {
            "doc_id": doc_id,
            "canonical_id": ev.payload.get("canonical_id") or "",
            "source": ev.payload.get("source") or "",
            "pdf_object_key": _infer_object_key_from_minio_url(file_url),
            "title": ev.payload.get("title") or "",
        }
        files = {"file": ("paper.pdf", pdf_bytes, "application/pdf")}
        pr = await client.post(_join(settings.parser_base_url, "/api/convert"), files=files, data=data)
        if pr.status_code >= 400:
            raise RuntimeError(f"parse failed: {pr.status_code} {pr.text[:200]!r}")
        parsed = pr.json()

    conn.execute("UPDATE doc_state SET status='PARSED', pdf_object_key=?, updated_at_unix=? WHERE doc_key=?", (data["pdf_object_key"], _now(), ev.doc_key))
    payload = {**ev.payload, "parsed": parsed}
    conn.execute(
        "INSERT INTO events(event_id, event_type, doc_key, payload_json, status, attempts, next_run_at_unix, created_at_unix) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (_new_id(), "PdfParsed", ev.doc_key, json.dumps(payload, ensure_ascii=False), "PENDING", 0, _now(), _now()),
    )
    _mark_event_done(conn, ev.event_id)


async def _transition_index(app: FastAPI, ev: Event) -> None:
    # PARSED -> INDEXED
    conn: sqlite3.Connection = app.state.db
    parsed = (ev.payload.get("parsed") or {})
    doc = parsed.get("doc") or {}
    chunks = parsed.get("chunks") or []
    summary_keywords = parsed.get("summary_keywords") or {}
    if not doc or not chunks:
        raise RuntimeError("parsed payload incomplete")
    async with httpx.AsyncClient(timeout=settings.http_timeout, trust_env=False) as client:
        resp = await client.post(_join(settings.indexing_base_url, "/index"), json={"doc": doc, "chunks": chunks, "summary_keywords": summary_keywords})
        if resp.status_code >= 400:
            raise RuntimeError(f"index failed: {resp.status_code} {resp.text[:200]!r}")
        _ = resp.json()

    conn.execute("UPDATE doc_state SET status='INDEXED', updated_at_unix=? WHERE doc_key=?", (_now(), ev.doc_key))
    conn.execute(
        "INSERT INTO events(event_id, event_type, doc_key, payload_json, status, attempts, next_run_at_unix, created_at_unix) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (_new_id(), "Indexed", ev.doc_key, json.dumps({"doc_id": doc.get("doc_id")}, ensure_ascii=False), "PENDING", 0, _now(), _now()),
    )
    _mark_event_done(conn, ev.event_id)


def _infer_object_key_from_minio_url(file_url: str) -> str:
    # http://localhost:9000/papers/<object>?X-Amz...
    path = file_url.split("?", 1)[0]
    if "://" in path:
        path = path.split("://", 1)[1]
        path = path.split("/", 1)[1]
    if path.startswith("papers/"):
        return path[len("papers/") :]
    return path


def _sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


async def _transition_dataset_index(app: FastAPI, ev: Event) -> None:
    """DatasetDiscovered -> Indexed (no download/parse)."""
    conn: sqlite3.Connection = app.state.db
    extra = ev.payload.get("extra") or {}
    title = (ev.payload.get("title") or "dataset").strip()
    desc = (ev.payload.get("description") or "").strip()
    ref = (extra.get("ref") or "").strip()
    if not ref:
        # try parse from url
        import re

        m = re.search(r"kaggle\.com/datasets/([^?\s]+)", ev.payload.get("url") or "")
        ref = m.group(1) if m else ""

    details: Dict[str, Any] = {
        "ref": ref,
        "url": ev.payload.get("url"),
        "title": title,
        "description": desc,
    }
    if settings.kaggle_username and settings.kaggle_key and ref and "/" in ref:
        owner, slug = ref.split("/", 1)
        api_url = f"https://www.kaggle.com/api/v1/datasets/view/{owner}/{slug}"
        async with httpx.AsyncClient(timeout=settings.http_timeout, trust_env=False) as client:
            resp = await client.get(api_url, auth=(settings.kaggle_username, settings.kaggle_key))
            if resp.status_code < 400:
                try:
                    details = resp.json()
                except Exception:
                    pass
            else:
                details["kaggle_error"] = {"status": resp.status_code, "body": resp.text[:300]}

    text = "Kaggle Dataset\n" + json.dumps(details, ensure_ascii=False, indent=2)
    content_sha = _sha256_hex(text.encode("utf-8"))
    doc_id = _sha256_hex(ev.doc_key.encode("utf-8"))[:32]
    doc = {
        "doc_id": doc_id,
        "canonical_id": ev.payload.get("canonical_id") or (f"kaggle:{ref}" if ref else ""),
        "doc_type": "dataset",
        "title": title,
        "authors": [],
        "year": None,
        "venue": "kaggle",
        "source": "kaggle",
        "license": "",
        "open_access": True,
        "pdf_object_key": "",
        "pdf_sha256": content_sha,
        "created_at_unix": _now(),
        "extra": {"ref": ref, "url": ev.payload.get("url")},
    }
    chunks = [
        {
            "chunk_id": f"{doc_id}:0",
            "doc_id": doc_id,
            "text": text,
            "span": None,
            "section_path": "dataset_details",
        }
    ]
    summary_keywords = {
        "summary": desc[:800],
        "summary_source": "generated_summary",
        "keywords": [],
    }
    async with httpx.AsyncClient(timeout=settings.http_timeout, trust_env=False) as client:
        resp = await client.post(
            _join(settings.indexing_base_url, "/index"),
            json={"doc": doc, "chunks": chunks, "summary_keywords": summary_keywords},
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"index failed: {resp.status_code} {resp.text[:200]!r}")

    conn.execute("UPDATE doc_state SET status='INDEXED', pdf_sha256=?, updated_at_unix=? WHERE doc_key=?", (content_sha, _now(), ev.doc_key))
    _mark_event_done(conn, ev.event_id)


async def _transition_code_index(app: FastAPI, ev: Event) -> None:
    """CodeDiscovered -> Indexed (no download/parse)."""
    conn: sqlite3.Connection = app.state.db
    extra = ev.payload.get("extra") or {}
    title = (ev.payload.get("title") or ev.payload.get("url") or "repo").strip()
    desc = (ev.payload.get("description") or "").strip()
    full_name = (extra.get("full_name") or "").strip()
    if not full_name:
        import re

        m = re.search(r"github\.com/([^/\s]+)/([^/\s]+)", ev.payload.get("url") or "")
        if m:
            full_name = f"{m.group(1)}/{m.group(2)}"

    headers = {"Accept": "application/vnd.github+json"}
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"

    repo: Dict[str, Any] = {}
    languages: Dict[str, Any] = {}
    readme_text = ""
    if full_name:
        async with httpx.AsyncClient(timeout=settings.http_timeout, trust_env=False, headers=headers) as client:
            r1 = await client.get(f"https://api.github.com/repos/{full_name}")
            if r1.status_code < 400:
                try:
                    repo = r1.json()
                except Exception:
                    repo = {}
            r2 = await client.get(f"https://api.github.com/repos/{full_name}/languages")
            if r2.status_code < 400:
                try:
                    languages = r2.json()
                except Exception:
                    languages = {}
            r3 = await client.get(
                f"https://api.github.com/repos/{full_name}/readme",
                headers={**headers, "Accept": "application/vnd.github.raw"},
            )
            if r3.status_code < 400:
                readme_text = (r3.text or "")[:20000]

    details = {
        "full_name": full_name,
        "url": ev.payload.get("url"),
        "repo": repo,
        "languages": languages,
        "readme": readme_text,
    }
    text = "GitHub Repository\n" + json.dumps(details, ensure_ascii=False, indent=2)
    content_sha = _sha256_hex(text.encode("utf-8"))
    doc_id = _sha256_hex(ev.doc_key.encode("utf-8"))[:32]
    doc = {
        "doc_id": doc_id,
        "canonical_id": ev.payload.get("canonical_id") or (f"github:{full_name}" if full_name else ""),
        "doc_type": "code",
        "title": title,
        "authors": [],
        "year": None,
        "venue": "github",
        "source": "github",
        "license": "",
        "open_access": True,
        "pdf_object_key": "",
        "pdf_sha256": content_sha,
        "created_at_unix": _now(),
        "extra": {"full_name": full_name, "url": ev.payload.get("url")},
    }
    chunks = [
        {
            "chunk_id": f"{doc_id}:0",
            "doc_id": doc_id,
            "text": text,
            "span": None,
            "section_path": "repo_details",
        }
    ]
    summary_keywords = {
        "summary": desc[:800],
        "summary_source": "generated_summary",
        "keywords": [],
    }
    async with httpx.AsyncClient(timeout=settings.http_timeout, trust_env=False) as client:
        resp = await client.post(
            _join(settings.indexing_base_url, "/index"),
            json={"doc": doc, "chunks": chunks, "summary_keywords": summary_keywords},
        )
        if resp.status_code >= 400:
            raise RuntimeError(f"index failed: {resp.status_code} {resp.text[:200]!r}")

    conn.execute("UPDATE doc_state SET status='INDEXED', pdf_sha256=?, updated_at_unix=? WHERE doc_key=?", (content_sha, _now(), ev.doc_key))
    _mark_event_done(conn, ev.event_id)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)
