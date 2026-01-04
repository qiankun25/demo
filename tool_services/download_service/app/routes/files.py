"""File query APIs for claim-check consumers."""

import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel, Field

from app.database import get_async_session
from app.models.file import DocumentFile
from app.services.storage import MinIOStorage
from app.config import settings


router = APIRouter(prefix="/files", tags=["files"])


class SignedURLResponse(BaseModel):
    file_id: str
    url: str = Field(..., description="Presigned download URL")
    expires_seconds: int


@router.get("/{file_id}/signed_url", response_model=SignedURLResponse)
async def get_signed_url(
    file_id: str,
    expires: int = None,
    session: AsyncSession = Depends(get_async_session),
) -> SignedURLResponse:
    try:
        file_uuid = uuid.UUID(file_id)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Invalid file_id UUID")

    result = await session.execute(select(DocumentFile).where(DocumentFile.id == file_uuid))
    f = result.scalar_one_or_none()
    if not f:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    # Use default expiration from config if not provided
    if expires is None:
        expires = settings.presigned_url_expires
    
    # Clamp expires value between min and max
    expires_clamped = max(settings.presigned_url_min_expires, min(expires, settings.presigned_url_max_expires))
    
    storage = MinIOStorage(
        endpoint=settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        bucket=f.minio_bucket,
        secure=settings.minio_secure,
        external_endpoint=settings.minio_external_endpoint,
        region=settings.aws_region,
    )
    url = storage.get_presigned_url(object_name=f.minio_object, expires=expires_clamped)
    return SignedURLResponse(file_id=str(f.id), url=url, expires_seconds=expires_clamped)


