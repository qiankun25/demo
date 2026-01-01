"""init discovery db

Revision ID: 0001_init_discovery_db
Revises:
Create Date: 2026-01-01
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_init_discovery_db"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "search_results",
        sa.Column("result_id", sa.String(length=64), primary_key=True),
        sa.Column("trace_id", sa.String(length=64), nullable=True),
        sa.Column("output_key", sa.Text(), nullable=False),
        sa.Column("query_hash", sa.String(length=128), nullable=True),
        sa.Column("created_at_unix", sa.Integer(), nullable=False),
    )

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
    )
    op.create_index("idx_outbox_status", "outbox_events", ["status"])


def downgrade() -> None:
    op.drop_index("idx_outbox_status", table_name="outbox_events")
    op.drop_table("outbox_events")
    op.drop_table("inbox_events")
    op.drop_table("search_results")


