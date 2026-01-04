"""add query hash

Revision ID: 0002_add_query_hash
Revises: 0001_create_search_results
Create Date: 2024-12-20 14:35:22.654321
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0002_add_query_hash'
down_revision: Union[str, None] = '0001_create_search_results'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("search_results", sa.Column("query_hash", sa.String(length=128), nullable=True))


def downgrade() -> None:
    op.drop_column("search_results", "query_hash")

