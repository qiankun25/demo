"""FastAPI routes for download task management."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime
from typing import Optional
import uuid

from app.database import get_async_session
from app.models.task import DownloadTask, TaskStatus
from app.models.file import DocumentFile
from app.celery_app import celery_app
from app.services.storage import MinIOStorage
from app.config import settings

router = APIRouter(prefix="/download", tags=["download"])


# Request/Response models
class DownloadRequest(BaseModel):
    """Request model for creating a download task."""
    url: str = Field(..., description="URL of the PDF to download")


class DownloadResponse(BaseModel):
    """Response model for download task creation."""
    task_id: str = Field(..., description="Unique task identifier")
    status: str = Field(..., description="Current task status")


class TaskStatusResponse(BaseModel):
    """Response model for task status query."""
    task_id: str = Field(..., description="Unique task identifier")
    status: str = Field(..., description="Current task status")
    file_url: Optional[str] = Field(None, description="Presigned URL for file download (only when status is success)")
    error_message: Optional[str] = Field(None, description="Error message if task failed")
    created_at: datetime = Field(..., description="Task creation timestamp")
    updated_at: datetime = Field(..., description="Task last update timestamp")


@router.post("", response_model=DownloadResponse, status_code=status.HTTP_201_CREATED)
async def create_download_task(
    request: DownloadRequest,
    session: AsyncSession = Depends(get_async_session)
) -> DownloadResponse:
    """Create a new download task.
    
    Accepts a PDF URL and creates an asynchronous download task. The task is
    enqueued to Celery for background processing.
    
    Args:
        request: Download request containing the URL
        session: Database session (injected)
    
    Returns:
        DownloadResponse with task_id and initial status
    
    Raises:
        HTTPException 422: If URL field is missing or invalid
    """
    # Create new download task with pending status
    new_task = DownloadTask(
        url=request.url,
        status=TaskStatus.PENDING
    )
    
    session.add(new_task)
    await session.commit()
    await session.refresh(new_task)
    
    # Enqueue task to Celery
    celery_app.send_task(
        "app.tasks.download_task.download_pdf_task",
        args=[str(new_task.id)]
    )
    
    return DownloadResponse(
        task_id=str(new_task.id),
        status=new_task.status.value
    )


@router.get("/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(
    task_id: str,
    session: AsyncSession = Depends(get_async_session)
) -> TaskStatusResponse:
    """Get the status of a download task.
    
    Retrieves the current status of a download task by its ID. If the task
    completed successfully, includes a presigned URL for file download.
    
    Args:
        task_id: UUID of the download task
        session: Database session (injected)
    
    Returns:
        TaskStatusResponse with task details and file URL if available
    
    Raises:
        HTTPException 404: If task not found
        HTTPException 422: If task_id is not a valid UUID
    """
    # Validate UUID format
    try:
        task_uuid = uuid.UUID(task_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid task_id format. Must be a valid UUID."
        )
    
    # Query task from database
    result = await session.execute(
        select(DownloadTask).where(DownloadTask.id == task_uuid)
    )
    task = result.scalar_one_or_none()
    
    if task is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Task with id {task_id} not found"
        )
    
    # Generate presigned URL if task succeeded
    file_url = None
    if task.status == TaskStatus.SUCCESS and task.file_id:
        try:
            # Query file separately to avoid lazy loading issues
            file_result = await session.execute(
                select(DocumentFile).where(DocumentFile.id == task.file_id)
            )
            file = file_result.scalar_one_or_none()
            
            if file:
                # Initialize MinIO storage service
                storage = MinIOStorage(
                    endpoint=settings.minio_endpoint,
                    access_key=settings.minio_access_key,
                    secret_key=settings.minio_secret_key,
                    bucket=settings.minio_bucket,
                    secure=settings.minio_secure,
                    external_endpoint=settings.minio_external_endpoint
                )
                
                # Generate presigned URL with 1 hour expiration
                file_url = storage.get_presigned_url(
                    object_name=file.minio_object,
                    expires=3600
                )
        except Exception as e:
            # Log error but don't fail the entire request
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to generate presigned URL for task {task_id}: {e}")
            # Return task status without file_url
    
    return TaskStatusResponse(
        task_id=str(task.id),
        status=task.status.value,
        file_url=file_url,
        error_message=task.error_message,
        created_at=task.created_at,
        updated_at=task.updated_at
    )
