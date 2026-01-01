"""init orchestration db

Revision ID: 0001_init_orchestration_db
Revises: 
Create Date: 2026-01-01
"""

from alembic import op
import sqlalchemy as sa


revision = "0001_init_orchestration_db"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "jobs",
        sa.Column("trace_id", sa.String(length=64), primary_key=True),
        sa.Column("task_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="init"),
        sa.Column("requested_limit", sa.Integer(), nullable=False, server_default="5"),
        sa.Column("metadata_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("context_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at_unix", sa.Integer(), nullable=False),
        sa.Column("updated_at_unix", sa.Integer(), nullable=False),
    )

    op.create_table(
        "work_items",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("trace_id", sa.String(length=64), nullable=False),
        sa.Column("work_key", sa.String(length=128), nullable=False),
        sa.Column("stage", sa.String(length=64), nullable=False, server_default="init"),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PENDING"),
        sa.Column("attempt", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_run_at_unix", sa.Integer(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("stage_output_refs_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("created_at_unix", sa.Integer(), nullable=False),
        sa.Column("updated_at_unix", sa.Integer(), nullable=False),
    )
    op.create_index("idx_work_items_trace_id", "work_items", ["trace_id"])
    op.create_index("uq_work_items_trace_work_key", "work_items", ["trace_id", "work_key"], unique=True)

    op.create_table(
        "artifacts_index",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("trace_id", sa.String(length=64), nullable=False),
        sa.Column("work_key", sa.String(length=128), nullable=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("ref_json", sa.Text(), nullable=False),
        sa.Column("created_at_unix", sa.Integer(), nullable=False),
    )
    op.create_index("idx_artifacts_trace_id", "artifacts_index", ["trace_id"])

    op.create_table(
        "inbox_events",
        sa.Column("event_id", sa.String(length=128), primary_key=True),
        sa.Column("trace_id", sa.String(length=64), nullable=False),
        sa.Column("received_at_unix", sa.Integer(), nullable=False),
    )

    op.create_table(
        "outbox_events",
        sa.Column("event_id", sa.String(length=128), primary_key=True),
        sa.Column("routing_key", sa.String(length=256), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="PENDING"),
        sa.Column("created_at_unix", sa.Integer(), nullable=False),
    )
    op.create_index("idx_outbox_status", "outbox_events", ["status"])


def downgrade() -> None:
    op.drop_index("idx_outbox_status", table_name="outbox_events")
    op.drop_table("outbox_events")
    op.drop_table("inbox_events")
    op.drop_index("idx_artifacts_trace_id", table_name="artifacts_index")
    op.drop_table("artifacts_index")
    op.drop_index("uq_work_items_trace_work_key", table_name="work_items")
    op.drop_index("idx_work_items_trace_id", table_name="work_items")
    op.drop_table("work_items")
    op.drop_table("jobs")


