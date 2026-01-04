"""add file metadata

Revision ID: 0002_add_file_metadata
Revises: 0001_create_document_file
Create Date: 2024-12-21 15:42:18.654321
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0002_add_file_metadata'
down_revision: Union[str, None] = '0001_create_document_file'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("document_file", sa.Column("mime_type", sa.Text(), nullable=False, server_default="application/octet-stream"))
    op.add_column("document_file", sa.Column("file_size", sa.Integer(), nullable=False, server_default="0"))
    op.create_index("idx_document_file_minio_object", "document_file", ["minio_bucket", "minio_object"])


def downgrade() -> None:
    op.drop_index("idx_document_file_minio_object", table_name="document_file")
    op.drop_column("document_file", "file_size")
    op.drop_column("document_file", "mime_type")

