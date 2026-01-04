"""add inbox events

Revision ID: 0003_add_inbox_events
Revises: 0002_add_query_hash
Create Date: 2024-12-25 09:12:45.789012
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0003_add_inbox_events'
down_revision: Union[str, None] = '0002_add_query_hash'
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


def downgrade() -> None:
    op.drop_table("inbox_events")

