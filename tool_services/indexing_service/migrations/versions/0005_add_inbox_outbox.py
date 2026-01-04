"""add inbox/outbox for mq

Revision ID: 0005_add_inbox_outbox
Revises: 0004_add_doc_metadata_and_chunk_fields
Create Date: 2024-12-30 20:15:50.123456
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0005_add_inbox_outbox'
down_revision: Union[str, None] = '0004_add_doc_metadata_and_chunk_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "inbox_events",
        sa.Column("event_id", sa.String(length=256), primary_key=True),
        sa.Column("routing_key", sa.String(length=256), nullable=False),
        sa.Column("trace_id", sa.String(length=64), nullable=False),
        sa.Column("received_at_unix", sa.Integer(), nullable=False),
    )

    op.create_table(
        "outbox_events",
        sa.Column("event_id", sa.String(length=256), primary_key=True),
        sa.Column("routing_key", sa.String(length=256), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PENDING"),
        sa.Column("created_at_unix", sa.Integer(), nullable=False),
        sa.Column("published_at_unix", sa.Integer(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
    )
    op.create_index("idx_outbox_status", "outbox_events", ["status"])


def downgrade() -> None:
    op.drop_index("idx_outbox_status", table_name="outbox_events")
    op.drop_table("outbox_events")
    op.drop_table("inbox_events")

