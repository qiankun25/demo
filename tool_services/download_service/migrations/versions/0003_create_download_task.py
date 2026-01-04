"""create download task

Revision ID: 0003_create_download_task
Revises: 0002_add_file_metadata
Create Date: 2024-12-26 10:18:55.789012
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = '0003_create_download_task'
down_revision: Union[str, None] = '0002_add_file_metadata'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "download_task",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("status", sa.Enum("pending", "downloading", "success", "failed", name="taskstatus"), nullable=False),
        sa.Column("file_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("document_file.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("idx_download_task_status", "download_task", ["status"])


def downgrade() -> None:
    op.drop_index("idx_download_task_status", table_name="download_task")
    op.drop_table("download_task")
    op.execute("DROP TYPE IF EXISTS taskstatus")

