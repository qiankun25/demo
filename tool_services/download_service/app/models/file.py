"""Document file model."""

import uuid
from datetime import datetime

from sqlalchemy import Column, String, Integer, Text, DateTime, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class DocumentFile(Base):
    """Document file model for storing file metadata."""
    
    __tablename__ = "document_file"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    file_name = Column(Text, nullable=False)
    minio_bucket = Column(Text, nullable=False)
    minio_object = Column(Text, nullable=False)
    mime_type = Column(Text, nullable=False)
    file_size = Column(Integer, nullable=False)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    
    # Relationship back to DownloadTask
    task = relationship("DownloadTask", back_populates="file", uselist=False)
    
    # Index for MinIO object lookup
    __table_args__ = (
        Index("idx_document_file_minio_object", "minio_bucket", "minio_object"),
    )
    
    def __repr__(self):
        return f"<DocumentFile(id={self.id}, file_name={self.file_name})>"
