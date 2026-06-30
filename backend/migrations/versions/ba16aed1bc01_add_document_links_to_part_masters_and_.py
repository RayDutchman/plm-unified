"""add_document_links_to_part_masters_and_drop_components

Revision ID: ba16aed1bc01
Revises: 4f3f1d68d681
Create Date: 2026-06-30 18:58:44.559979

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'ba16aed1bc01'
down_revision: Union[str, None] = '4f3f1d68d681'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('part_masters', sa.Column('document_links', postgresql.JSONB(astext_type=sa.Text()), nullable=True))
    op.execute("DROP TABLE IF EXISTS component_attachments CASCADE")
    op.drop_table('components')


def downgrade() -> None:
    op.create_table('components',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('code', sa.String(length=64), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('spec', sa.String(length=255), nullable=True),
    sa.Column('version', sa.String(length=32), nullable=True),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('remark', sa.Text(), nullable=True),
    sa.Column('revisions', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('revision_parent_id', sa.UUID(), nullable=True),
    sa.Column('creator_id', sa.UUID(), nullable=True),
    sa.Column('document_links', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('component_attachments',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('part_master_id', sa.UUID(), nullable=False),
    sa.Column('category', sa.String(length=32), nullable=False),
    sa.Column('file_name', sa.String(length=255), nullable=True),
    sa.Column('file_size', sa.Integer(), nullable=True),
    sa.Column('file_path', sa.String(length=512), nullable=True),
    sa.Column('file_hash', sa.String(length=64), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['part_master_id'], ['part_masters.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.drop_column('part_masters', 'document_links')
