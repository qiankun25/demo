"""create docs

Revision ID: 0001_create_docs
Revises:
Create Date: 2024-12-17 09:15:30.123456
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0001_create_docs'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('docs',
    sa.Column('doc_id', sa.String(), nullable=False),
    sa.Column('canonical_id', sa.String(), nullable=True),
    sa.Column('doc_type', sa.String(), nullable=True),
    sa.Column('title', sa.Text(), nullable=True),
    sa.Column('created_at_unix', sa.BigInteger(), nullable=True),
    sa.PrimaryKeyConstraint('doc_id')
    )
    op.create_index(op.f('ix_docs_doc_id'), 'docs', ['doc_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_docs_doc_id'), table_name='docs')
    op.drop_table('docs')

