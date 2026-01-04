"""create parsed docs

Revision ID: 0001_create_parsed_docs
Revises:
Create Date: 2024-12-18 08:42:15.123456
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0001_create_parsed_docs'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "parsed_docs",
        sa.Column("doc_id", sa.String(length=64), primary_key=True),
        sa.Column("output_key", sa.Text(), nullable=False),
        sa.Column("created_at_unix", sa.Integer(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("parsed_docs")

