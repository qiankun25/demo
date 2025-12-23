"""Celery tasks module."""

from app.tasks.download_task import download_pdf_task

__all__ = ["download_pdf_task"]
