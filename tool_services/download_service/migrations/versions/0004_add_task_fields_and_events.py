"""add task fields and events

Revision ID: 0004_add_task_fields_and_events
Revises: 0003_create_download_task
Create Date: 2024-12-31 13:25:40.456789
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0004_add_task_fields_and_events'
down_revision: Union[str, None] = '0003_create_download_task'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("download_task", sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"))
    op.add_column("download_task", sa.Column("error_message", sa.Text(), nullable=True))
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
    op.drop_column("download_task", "error_message")
    op.drop_column("download_task", "retry_count")

