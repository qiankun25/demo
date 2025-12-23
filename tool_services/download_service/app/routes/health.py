"""Health check endpoints."""

from fastapi import APIRouter, status, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from redis import Redis

from app.database import get_async_session
from app.config import settings
from app.services.storage import MinIOStorage


router = APIRouter(tags=["health"])


@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check(db: AsyncSession = Depends(get_async_session)):
    """Comprehensive health check endpoint.
    
    Checks:
    - API service is running
    - Database connectivity
    - Redis connectivity
    - Object storage connectivity
    
    Returns:
        dict: Health status of all components
    """
    health_status = {
        "status": "healthy",
        "components": {}
    }
    
    # Check database
    try:
        await db.execute(text("SELECT 1"))
        health_status["components"]["database"] = "ok"
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["components"]["database"] = f"error: {str(e)}"
    
    # Check Redis
    try:
        redis_client = Redis.from_url(settings.redis_url)
        redis_client.ping()
        health_status["components"]["redis"] = "ok"
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["components"]["redis"] = f"error: {str(e)}"
    
    # Check object storage
    try:
        storage = MinIOStorage(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            bucket=settings.minio_bucket,
            secure=settings.minio_secure,
            external_endpoint=settings.minio_external_endpoint
        )
        bucket_exists = storage.client.bucket_exists(storage.bucket)
        if bucket_exists:
            health_status["components"]["storage"] = "ok"
        else:
            health_status["status"] = "unhealthy"
            health_status["components"]["storage"] = "bucket not found"
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["components"]["storage"] = f"error: {str(e)}"
    
    # Return appropriate status code
    if health_status["status"] == "unhealthy":
        return health_status, status.HTTP_503_SERVICE_UNAVAILABLE
    
    return health_status


@router.get("/health/live", status_code=status.HTTP_200_OK)
async def liveness_check():
    """Liveness probe for Kubernetes/container orchestration.
    
    Returns:
        dict: Simple alive status
    """
    return {"status": "alive"}


@router.get("/health/ready", status_code=status.HTTP_200_OK)
async def readiness_check(db: AsyncSession = Depends(get_async_session)):
    """Readiness probe for Kubernetes/container orchestration.
    
    Checks if service is ready to accept traffic.
    
    Returns:
        dict: Readiness status
    """
    try:
        # Check critical dependencies
        await db.execute(text("SELECT 1"))
        
        redis_client = Redis.from_url(settings.redis_url)
        redis_client.ping()
        
        return {"status": "ready"}
    except Exception as e:
        return {"status": "not ready", "error": str(e)}, status.HTTP_503_SERVICE_UNAVAILABLE
