"""add doc metadata and chunk fields

Revision ID: 0004_add_doc_metadata_and_chunk_fields
Revises: 0003_create_chunks
Create Date: 2024-12-29 17:38:25.456789
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0004_add_doc_metadata_and_chunk_fields'
down_revision: Union[str, None] = '0003_create_chunks'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('docs', sa.Column('license', sa.Text(), nullable=True))
    op.add_column('docs', sa.Column('open_access', sa.Integer(), nullable=True))
    op.add_column('docs', sa.Column('pdf_object_key', sa.Text(), nullable=True))
    op.add_column('docs', sa.Column('extra_json', sa.Text(), nullable=True))

    op.add_column('chunks', sa.Column('page', sa.Integer(), nullable=True))
    op.add_column('chunks', sa.Column('paragraph', sa.Integer(), nullable=True))
    op.add_column('chunks', sa.Column('section_path', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('chunks', 'section_path')
    op.drop_column('chunks', 'paragraph')
    op.drop_column('chunks', 'page')
    op.drop_column('docs', 'extra_json')
    op.drop_column('docs', 'pdf_object_key')
    op.drop_column('docs', 'open_access')
    op.drop_column('docs', 'license')

