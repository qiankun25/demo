"""add outbox events

Revision ID: 0004_add_outbox_events
Revises: 0003_add_inbox_events
Create Date: 2024-12-31 18:50:20.456789
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0004_add_outbox_events'
down_revision: Union[str, None] = '0003_add_inbox_events'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
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

