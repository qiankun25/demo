"""Download task model."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Column, String, Integer, Text, DateTime, Enum, ForeignKey, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class TaskStatus(str, enum.Enum):
    """Task status enumeration."""
    PENDING = "pending"
    DOWNLOADING = "downloading"
    SUCCESS = "success"
    FAILED = "failed"


class DownloadTask(Base):
    """Download task model for tracking PDF download operations."""
    
    __tablename__ = "download_task"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    url = Column(Text, nullable=False)
    status = Column(Enum(TaskStatus), nullable=False, default=TaskStatus.PENDING)
    retry_count = Column(Integer, nullable=False, default=0)
    error_message = Column(Text, nullable=True)
    file_id = Column(UUID(as_uuid=True), ForeignKey("document_file.id"), nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship to DocumentFile
    file = relationship("DocumentFile", back_populates="task", uselist=False)
    
    # Indexes for performance
    __table_args__ = (
        Index("idx_download_task_status", "status"),
        Index("idx_download_task_created_at", "created_at"),
    )
    
    def __repr__(self):
        return f"<DownloadTask(id={self.id}, url={self.url}, status={self.status})>"
