"""FastAPI application entry point for Literature Download Service."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.routes import health
from app.routes.download import router as download_router
from app.routes.upload import router as upload_router
from app.config import settings
from app.services.storage import MinIOStorage


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup: Initialize database tables
    await init_db()
    
    # Ensure storage bucket exists
    try:
        storage = MinIOStorage(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            bucket=settings.minio_bucket,
            secure=settings.minio_secure,
            external_endpoint=settings.minio_external_endpoint
        )
        storage.ensure_bucket_exists()
    except Exception as e:
        print(f"Warning: Failed to initialize storage bucket: {e}")
    
    yield
    # Shutdown: cleanup if needed (currently none)


# Initialize FastAPI application
app = FastAPI(
    title="Literature Download Service",
    description="Asynchronous PDF download service for academic literature",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs" if not settings.is_production else None,  # Disable docs in production
    redoc_url="/redoc" if not settings.is_production else None,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router)
app.include_router(download_router)
app.include_router(upload_router)
