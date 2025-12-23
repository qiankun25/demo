"""Celery task for downloading PDF files asynchronously."""

import logging
import traceback
from datetime import datetime
from typing import Optional

from celery import Task
from celery.exceptions import MaxRetriesExceededError
from httpx import RequestError, HTTPStatusError
from minio.error import S3Error
from sqlalchemy.orm import Session

from app.celery_app import celery_app
from app.database import SessionLocal
from app.models.task import DownloadTask, TaskStatus
from app.models.file import DocumentFile
from app.services.validator import URLValidator
from app.services.downloader import PDFDownloader
from app.services.storage import MinIOStorage
from app.config import settings

logger = logging.getLogger(__name__)


class DownloadTaskWithRetry(Task):
    """Custom Celery task class with retry configuration."""
    autoretry_for = (RequestError, HTTPStatusError, S3Error, ConnectionError)
    retry_backoff = True
    retry_backoff_max = 600
    retry_jitter = True


@celery_app.task(
    bind=True,
    base=DownloadTaskWithRetry,
    max_retries=3,
    name="app.tasks.download_task.download_pdf_task"
)
def download_pdf_task(self, task_id: str) -> dict:
    """
    Download PDF file from URL and store in MinIO.
    
    This task implements the complete download pipeline:
    1. Update task status to "downloading"
    2. Validate URL reachability
    3. Download PDF file
    4. Upload to MinIO storage
    5. Create DocumentFile record
    6. Update task status to "success"
    
    On failure, implements exponential backoff retry logic:
    - Attempt 1: Immediate
    - Attempt 2: 5 seconds delay
    - Attempt 3: 25 seconds delay (5 * 2^2)
    - Attempt 4: 125 seconds delay (5 * 2^3)
    
    Args:
        task_id: UUID of the DownloadTask record
    
    Returns:
        dict: Task result with status and file information
    
    Raises:
        MaxRetriesExceededError: If all retry attempts are exhausted
    """
    db: Optional[Session] = None
    
    try:
        # Get database session
        db = SessionLocal()
        
        # Fetch task from database
        task = db.query(DownloadTask).filter(DownloadTask.id == task_id).first()
        if not task:
            logger.error(f"Task not found: {task_id}")
            raise ValueError(f"Task {task_id} not found in database")
        
        logger.info(
            "download_started",
            extra={
                "task_id": task_id,
                "url": task.url,
                "attempt": self.request.retries + 1,
                "max_retries": self.max_retries
            }
        )
        
        # Update status to "downloading"
        task.status = TaskStatus.DOWNLOADING
        task.retry_count = self.request.retries
        task.updated_at = datetime.utcnow()
        db.commit()
        
        # Step 1: Validate URL reachability
        logger.debug(f"Validating URL: {task.url}")
        validator = URLValidator(timeout=10)
        
        # Run async validation in sync context
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            is_valid, error_message = loop.run_until_complete(
                validator.is_reachable(task.url)
            )
        finally:
            loop.close()
        
        if not is_valid:
            error_msg = f"URL validation failed: {error_message}"
            logger.warning(f"URL not reachable: {task.url} - {error_message}")
            raise ValueError(error_msg)
        
        logger.info(f"URL validated successfully: {task.url}")
        
        # Step 2: Download PDF file
        logger.debug(f"Downloading PDF from: {task.url}")
        downloader = PDFDownloader(timeout=30)
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            file_content, filename = loop.run_until_complete(
                downloader.download(task.url)
            )
        finally:
            loop.close()
        
        file_size = len(file_content)
        logger.info(f"Downloaded file: {filename} ({file_size} bytes)")
        
        # Step 3: Upload to MinIO storage
        logger.debug(f"Uploading file to MinIO: {filename}")
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
            task_id=task_id,
            filename=filename,
            content_type="application/pdf"
        )
        
        logger.info(f"File uploaded to MinIO: {object_name}")
        
        # Step 4: Create DocumentFile record
        document_file = DocumentFile(
            file_name=filename,
            minio_bucket=settings.minio_bucket,
            minio_object=object_name,
            mime_type="application/pdf",
            file_size=file_size,
            created_at=datetime.utcnow()
        )
        db.add(document_file)
        db.flush()  # Get the ID without committing
        
        # Step 5: Update task with success status
        task.status = TaskStatus.SUCCESS
        task.file_id = document_file.id
        task.error_message = None
        task.updated_at = datetime.utcnow()
        db.commit()
        
        logger.info(
            "download_completed",
            extra={
                "task_id": task_id,
                "file_id": str(document_file.id),
                "file_name": filename,
                "file_size": file_size
            }
        )
        
        return {
            "status": "success",
            "task_id": task_id,
            "file_id": str(document_file.id),
            "file_name": filename,
            "file_size": file_size
        }
    
    except MaxRetriesExceededError:
        # All retries exhausted - mark as failed
        error_msg = f"Max retries ({self.max_retries}) exceeded"
        logger.error(
            "download_failed_max_retries",
            extra={
                "task_id": task_id,
                "error": error_msg,
                "retries": self.request.retries
            }
        )
        
        if db:
            task = db.query(DownloadTask).filter(DownloadTask.id == task_id).first()
            if task:
                task.status = TaskStatus.FAILED
                task.error_message = error_msg
                task.retry_count = self.request.retries
                task.updated_at = datetime.utcnow()
                db.commit()
        
        raise
    
    except Exception as exc:
        # Log the error with full traceback
        error_msg = str(exc)
        error_trace = traceback.format_exc()
        
        logger.error(
            "download_failed",
            extra={
                "task_id": task_id,
                "error": error_msg,
                "traceback": error_trace,
                "attempt": self.request.retries + 1,
                "max_retries": self.max_retries
            }
        )
        
        # Update retry count in database
        if db:
            task = db.query(DownloadTask).filter(DownloadTask.id == task_id).first()
            if task:
                task.retry_count = self.request.retries + 1
                task.updated_at = datetime.utcnow()
                
                # If this is the last retry, mark as failed
                if self.request.retries >= self.max_retries:
                    task.status = TaskStatus.FAILED
                    task.error_message = error_msg
                    logger.error(f"Task failed after {self.max_retries} retries: {task_id}")
                
                db.commit()
        
        # Retry with exponential backoff if retries remaining
        if self.request.retries < self.max_retries:
            # Calculate exponential backoff: 5 * (2 ** retry_count)
            # Retry 0: 5s, Retry 1: 10s, Retry 2: 20s, Retry 3: 40s
            countdown = 5 * (2 ** self.request.retries)
            logger.info(f"Retrying task {task_id} in {countdown} seconds (attempt {self.request.retries + 2}/{self.max_retries + 1})")
            
            raise self.retry(exc=exc, countdown=countdown)
        else:
            # No more retries - mark as failed
            if db:
                task = db.query(DownloadTask).filter(DownloadTask.id == task_id).first()
                if task:
                    task.status = TaskStatus.FAILED
                    task.error_message = error_msg
                    task.updated_at = datetime.utcnow()
                    db.commit()
            
            raise
    
    finally:
        # Clean up database session
        if db:
            db.close()
