"""FastAPI routes for file upload management."""

from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime
from typing import List, Optional
import uuid
import logging

from app.database import get_async_session
from app.models.file import DocumentFile
from app.services.storage import MinIOStorage
from app.config import settings

router = APIRouter(prefix="/upload", tags=["upload"])
logger = logging.getLogger(__name__)


# Response models
class FileUploadResult(BaseModel):
    """Result model for individual file upload."""
    file_name: str = Field(..., description="Original filename")
    status: str = Field(..., description="Upload status: 'success' or 'failed'")
    file_id: Optional[str] = Field(None, description="Unique file identifier (UUID)")
    file_size: Optional[int] = Field(None, description="File size in bytes")
    mime_type: Optional[str] = Field(None, description="MIME type of the file")
    presigned_url: Optional[str] = Field(None, description="Presigned URL for file access")
    expires_in: Optional[int] = Field(None, description="URL expiration time in seconds")
    error_message: Optional[str] = Field(None, description="Error message if upload failed")
    created_at: Optional[datetime] = Field(None, description="Upload timestamp")


class BatchUploadResponse(BaseModel):
    """Response model for batch file upload."""
    total: int = Field(..., description="Total number of files")
    success: int = Field(..., description="Number of successfully uploaded files")
    failed: int = Field(..., description="Number of failed uploads")
    results: List[FileUploadResult] = Field(..., description="Individual file upload results")


def validate_pdf_file(file: UploadFile) -> Optional[str]:
    """Validate if the uploaded file is a PDF.
    
    Args:
        file: Uploaded file object
    
    Returns:
        Error message if validation fails, None if valid
    """
    # Check file extension
    if not file.filename:
        return "Filename is missing"
    
    if not file.filename.lower().endswith('.pdf'):
        return "File must be a PDF (extension check failed)"
    
    # Check MIME type if available
    if file.content_type and file.content_type != "application/pdf":
        return f"Invalid MIME type: {file.content_type}. Expected application/pdf"
    
    return None


async def process_single_file(
    file: UploadFile,
    expires: int,
    session: AsyncSession
) -> FileUploadResult:
    """Process a single file upload.
    
    Args:
        file: Uploaded file object
        expires: Presigned URL expiration time in seconds
        session: Database session
    
    Returns:
        FileUploadResult with upload status and details
    """
    file_name = file.filename or "unknown.pdf"
    
    try:
        # Validate file type
        validation_error = validate_pdf_file(file)
        if validation_error:
            return FileUploadResult(
                file_name=file_name,
                status="failed",
                error_message=validation_error
            )
        
        # Read file content
        file_content = await file.read()
        file_size = len(file_content)
        
        # Validate file size
        if file_size > settings.max_file_size:
            max_size_mb = settings.max_file_size / (1024 * 1024)
            return FileUploadResult(
                file_name=file_name,
                status="failed",
                error_message=f"File size exceeds limit ({max_size_mb:.0f}MB)"
            )
        
        if file_size == 0:
            return FileUploadResult(
                file_name=file_name,
                status="failed",
                error_message="File is empty"
            )
        
        # Generate unique file ID
        file_id = str(uuid.uuid4())
        
        # Upload to MinIO
        storage = MinIOStorage(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            bucket=settings.minio_bucket,
            secure=settings.minio_secure,
            external_endpoint=settings.minio_external_endpoint
        )
        
        object_name = storage.upload_file(
            file_content=file_content,
            task_id=file_id,
            filename=file_name,
            content_type="application/pdf"
        )
        
        logger.info(f"File uploaded to MinIO: {object_name} ({file_size} bytes)")
        
        # Create DocumentFile record
        document_file = DocumentFile(
            id=uuid.UUID(file_id),
            file_name=file_name,
            minio_bucket=settings.minio_bucket,
            minio_object=object_name,
            mime_type="application/pdf",
            file_size=file_size,
            created_at=datetime.utcnow()
        )
        
        session.add(document_file)
        await session.commit()
        await session.refresh(document_file)
        
        logger.info(f"DocumentFile record created: {file_id}")
        
        # Generate presigned URL
        presigned_url = storage.get_presigned_url(
            object_name=object_name,
            expires=expires
        )
        
        return FileUploadResult(
            file_name=file_name,
            status="success",
            file_id=file_id,
            file_size=file_size,
            mime_type="application/pdf",
            presigned_url=presigned_url,
            expires_in=expires,
            created_at=document_file.created_at
        )
        
    except Exception as e:
        logger.error(f"Failed to upload file {file_name}: {e}", exc_info=True)
        # Rollback the current transaction for this file
        await session.rollback()
        return FileUploadResult(
            file_name=file_name,
            status="failed",
            error_message=f"Upload failed: {str(e)}"
        )


@router.post("", response_model=BatchUploadResponse, status_code=status.HTTP_200_OK)
async def upload_files(
    files: List[UploadFile] = File(..., description="Multiple PDF files to upload"),
    expires: int = Query(
        default=3600,
        ge=60,
        le=604800,
        description="Presigned URL expiration time in seconds (60s - 7 days)"
    ),
    session: AsyncSession = Depends(get_async_session)
) -> BatchUploadResponse:
    """Upload multiple PDF files to MinIO storage.
    
    Accepts multiple PDF files and uploads them to MinIO with individual
    success/failure tracking. Failed uploads do not affect successful ones.
    
    Args:
        files: List of uploaded files
        expires: Presigned URL expiration time in seconds (default: 3600)
        session: Database session (injected)
    
    Returns:
        BatchUploadResponse with overall statistics and individual file results
    
    Raises:
        HTTPException 422: If no files provided or validation fails
    """
    if not files:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No files provided"
        )
    
    logger.info(f"Processing batch upload of {len(files)} files")
    
    results = []
    success_count = 0
    failed_count = 0
    
    # Process each file independently
    for file in files:
        result = await process_single_file(file, expires, session)
        results.append(result)
        
        if result.status == "success":
            success_count += 1
        else:
            failed_count += 1
    
    logger.info(
        f"Batch upload completed: {success_count} succeeded, {failed_count} failed"
    )
    
    return BatchUploadResponse(
        total=len(files),
        success=success_count,
        failed=failed_count,
        results=results
    )

