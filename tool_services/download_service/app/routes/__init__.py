"""Routes package for FastAPI application."""

from app.routes.download import router as download_router

__all__ = ["download_router"]
