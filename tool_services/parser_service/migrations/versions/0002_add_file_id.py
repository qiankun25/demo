"""add file id

Revision ID: 0002_add_file_id
Revises: 0001_create_parsed_docs
Create Date: 2024-12-23 12:55:30.654321
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0002_add_file_id'
down_revision: Union[str, None] = '0001_create_parsed_docs'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("parsed_docs", sa.Column("file_id", sa.String(length=64), nullable=True))


def downgrade() -> None:
    op.drop_column("parsed_docs", "file_id")

