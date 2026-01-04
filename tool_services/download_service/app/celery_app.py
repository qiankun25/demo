"""Celery application configuration for asynchronous task processing."""

from celery import Celery
from app.config import settings

# Initialize Celery app
celery_app = Celery(
    "literature_download_service",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_default_retry_delay=settings.celery_task_default_retry_delay,
    task_annotations={
        "*": {
            "max_retries": settings.max_retries,
        }
    },
    task_track_started=True,  # Track when tasks start
    task_time_limit=settings.celery_task_time_limit,
    task_soft_time_limit=settings.celery_task_soft_time_limit,
)

# Import tasks to register them with Celery
# This ensures tasks are discovered when the worker starts
try:
    from app.tasks import download_task  # noqa: F401
except ImportError:
    # Tasks module may not exist yet during initial setup
    pass
