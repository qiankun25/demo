"""add doc fields

Revision ID: 0002_add_doc_fields
Revises: 0001_create_docs
Create Date: 2024-12-22 11:28:45.654321
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '0002_add_doc_fields'
down_revision: Union[str, None] = '0001_create_docs'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('docs', sa.Column('authors_json', sa.Text(), nullable=True))
    op.add_column('docs', sa.Column('year', sa.Integer(), nullable=True))
    op.add_column('docs', sa.Column('venue', sa.Text(), nullable=True))
    op.add_column('docs', sa.Column('source', sa.Text(), nullable=True))
    op.add_column('docs', sa.Column('pdf_sha256', sa.String(), nullable=True))
    op.create_index(op.f('ix_docs_canonical_id'), 'docs', ['canonical_id'], unique=False)
    op.create_index(op.f('ix_docs_doc_type'), 'docs', ['doc_type'], unique=False)
    op.create_index(op.f('ix_docs_pdf_sha256'), 'docs', ['pdf_sha256'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_docs_pdf_sha256'), table_name='docs')
    op.drop_index(op.f('ix_docs_doc_type'), table_name='docs')
    op.drop_index(op.f('ix_docs_canonical_id'), table_name='docs')
    op.drop_column('docs', 'pdf_sha256')
    op.drop_column('docs', 'source')
    op.drop_column('docs', 'venue')
    op.drop_column('docs', 'year')
    op.drop_column('docs', 'authors_json')

