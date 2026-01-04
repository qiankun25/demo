"""create document file

Revision ID: 0001_create_document_file
Revises:
Create Date: 2024-12-16 11:30:20.123456
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '0001_create_document_file'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "document_file",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("file_name", sa.Text(), nullable=False),
        sa.Column("minio_bucket", sa.Text(), nullable=False),
        sa.Column("minio_object", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("document_file")

