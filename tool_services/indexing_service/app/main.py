from contextlib import asynccontextmanager
import os
import time
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi import status
from fastapi.responses import JSONResponse
import chromadb
from app.core.config import settings
from app.database.session import engine
from app.routes import index, search, kb

@asynccontextmanager
async def lifespan(app: FastAPI):
    # P0: migrations must be run via separate job, not at app startup.
    # Initialize Chroma
    os.makedirs(settings.CHROMA_PERSIST_DIR, exist_ok=True)
    chroma_client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
    collection = chroma_client.get_or_create_collection(
        name=settings.CHROMA_COLLECTION,
        metadata={"hnsw:space": settings.CHROMA_DISTANCE},
    )
    app.state.chroma_client = chroma_client
    app.state.chroma_collection = collection

    yield

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(index.router, tags=["index"])
app.include_router(search.router, tags=["search"])
app.include_router(kb.router, tags=["kb"])

@app.get("/health")
async def health():
    ready = await health_ready()
    code = ready.status_code
    payload = ready.body
    try:
        import json

        shaped = json.loads(payload.decode("utf-8"))
    except Exception:
        shaped = {"status": "unknown", "raw": str(payload)}
    shaped.setdefault("service", "indexing_service")
    shaped.setdefault("timestamp", time.time())
    return JSONResponse(status_code=code, content=shaped)


@app.get("/health/live")
async def health_live():
    return {"status": "alive"}


@app.get("/health/ready")
async def health_ready():
    components = {}
    ok = True

    # DB connectivity
    try:
        with engine.connect() as conn:
            conn.exec_driver_sql("SELECT 1")
        components["database"] = "ok"
    except Exception as e:
        ok = False
        components["database"] = f"error: {e}"

    # Vector store readiness (Chroma)
    try:
        coll = getattr(app.state, "chroma_collection", None)
        if coll is None:
            raise RuntimeError("chroma_collection not initialized")
        # best-effort lightweight call
        _ = coll.name
        components["vector_store"] = "ok"
        components["collection"] = coll.name
    except Exception as e:
        ok = False
        components["vector_store"] = f"error: {e}"

    status_code = status.HTTP_200_OK if ok else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(status_code=status_code, content={"status": "ready" if ok else "not ready", "components": components})

