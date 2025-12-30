import os
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import chromadb
from app.core.config import settings
from app.database.session import engine, Base
from app.routes import index, search, kb
from nexus_tool.tool_service import IndexerToolService

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize Database
    # Run migrations on startup
    from alembic.config import Config
    from alembic import command
    alembic_cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    command.upgrade(alembic_cfg, "head")
    
    # Initialize Chroma
    os.makedirs(settings.CHROMA_PERSIST_DIR, exist_ok=True)
    chroma_client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
    collection = chroma_client.get_or_create_collection(
        name=settings.CHROMA_COLLECTION,
        metadata={"hnsw:space": settings.CHROMA_DISTANCE},
    )
    app.state.chroma_client = chroma_client
    app.state.chroma_collection = collection

    # Start RabbitMQ Worker if needed
    service = IndexerToolService()
    worker_task = asyncio.create_task(service.start())

    yield
    
    # Cleanup
    worker_task.cancel()
    try:
        await worker_task
    except asyncio.CancelledError:
        pass

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
    return {
        "status": "ok", 
        "vector_store": "chroma", 
        "collection": app.state.chroma_collection.name,
        "database": engine.name
    }

