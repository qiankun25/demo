"""create search results

Revision ID: 0001_create_search_results
Revises:
Create Date: 2024-12-15 10:23:15.123456
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0001_create_search_results'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "search_results",
        sa.Column("result_id", sa.String(length=64), primary_key=True),
        sa.Column("trace_id", sa.String(length=64), nullable=True),
        sa.Column("output_key", sa.Text(), nullable=False),
        sa.Column("created_at_unix", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("search_results")

