"""init download db

Revision ID: 0001_init_download_db
Revises:
Create Date: 2026-01-01
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0001_init_download_db"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "document_file",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("file_name", sa.Text(), nullable=False),
        sa.Column("minio_bucket", sa.Text(), nullable=False),
        sa.Column("minio_object", sa.Text(), nullable=False),
        sa.Column("mime_type", sa.Text(), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("idx_document_file_minio_object", "document_file", ["minio_bucket", "minio_object"])

    op.create_table(
        "download_task",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("status", sa.Enum("pending", "downloading", "success", "failed", name="taskstatus"), nullable=False),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("file_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("document_file.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_index("idx_download_task_status", "download_task", ["status"])
    op.create_index("idx_download_task_created_at", "download_task", ["created_at"])

    op.create_table(
        "inbox_event",
        sa.Column("id", sa.Text(), primary_key=True),
        sa.Column("routing_key", sa.Text(), nullable=False),
        sa.Column("trace_id", sa.Text(), nullable=True),
        sa.Column("received_at", sa.DateTime(), nullable=False),
    )

    op.create_table(
        "outbox_event",
        sa.Column("event_id", sa.Text(), primary_key=True),
        sa.Column("routing_key", sa.Text(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="PENDING"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
    )
    op.create_index("idx_outbox_event_status", "outbox_event", ["status"])


def downgrade() -> None:
    op.drop_index("idx_outbox_event_status", table_name="outbox_event")
    op.drop_table("outbox_event")
    op.drop_table("inbox_event")
    op.drop_index("idx_download_task_created_at", table_name="download_task")
    op.drop_index("idx_download_task_status", table_name="download_task")
    op.drop_table("download_task")
    op.drop_index("idx_document_file_minio_object", table_name="document_file")
    op.drop_table("document_file")
    op.execute("DROP TYPE IF EXISTS taskstatus")


