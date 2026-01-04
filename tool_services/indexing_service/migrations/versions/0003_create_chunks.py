"""create chunks

Revision ID: 0003_create_chunks
Revises: 0002_add_doc_fields
Create Date: 2024-12-27 14:52:10.789012
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0003_create_chunks'
down_revision: Union[str, None] = '0002_add_doc_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('chunks',
    sa.Column('chunk_id', sa.String(), nullable=False),
    sa.Column('doc_id', sa.String(), nullable=True),
    sa.Column('text', sa.Text(), nullable=False),
    sa.ForeignKeyConstraint(['doc_id'], ['docs.doc_id'], ),
    sa.PrimaryKeyConstraint('chunk_id')
    )
    op.create_index(op.f('ix_chunks_chunk_id'), 'chunks', ['chunk_id'], unique=False)
    op.create_index(op.f('ix_chunks_doc_id'), 'chunks', ['doc_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_chunks_doc_id'), table_name='chunks')
    op.drop_index(op.f('ix_chunks_chunk_id'), table_name='chunks')
    op.drop_table('chunks')

