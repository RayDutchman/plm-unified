"""add documents tables

Revision ID: 13dd9ea3a0da
Revises: 63200c435bd2
Create Date: 2026-06-30 16:12:27.109314

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '13dd9ea3a0da'
down_revision: Union[str, None] = '63200c435bd2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('document_attachments',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('file_name', sa.String(length=500), nullable=False),
    sa.Column('file_size', sa.BigInteger(), nullable=False),
    sa.Column('file_path', sa.String(length=1000), nullable=False),
    sa.Column('file_hash', sa.String(length=64), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    # add document_id FK back after documents table is created
    op.add_column('document_attachments', sa.Column('document_id', sa.Uuid(), nullable=True))

    op.create_table('documents',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('code', sa.String(length=64), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('version', sa.String(length=10), nullable=False),
    sa.Column('status', sa.String(length=32), nullable=False),
    sa.Column('remark', sa.Text(), nullable=True),
    sa.Column('file_name', sa.String(length=500), nullable=True),
    sa.Column('file_id', sa.Uuid(), nullable=True),
    sa.Column('creator_id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.ForeignKeyConstraint(['creator_id'], ['users.id'], ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['file_id'], ['document_attachments.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_foreign_key(
        'fk_document_attachments_document_id',
        'document_attachments', 'documents',
        ['document_id'], ['id'],
        ondelete='CASCADE',
    )
    op.alter_column('document_attachments', 'document_id', nullable=False)

    op.create_table('document_group_links',
    sa.Column('document_id', sa.Uuid(), nullable=False),
    sa.Column('group_id', sa.Uuid(), nullable=False),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['group_id'], ['user_groups.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('document_id', 'group_id')
    )
    op.create_table('document_links',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('document_id', sa.Uuid(), nullable=False),
    sa.Column('entity_type', sa.String(length=32), nullable=False),
    sa.Column('entity_id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['document_id'], ['documents.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('document_links')
    op.drop_table('document_group_links')
    op.drop_table('documents')
    op.drop_constraint('fk_document_attachments_document_id', 'document_attachments', type_='foreignkey')
    op.drop_column('document_attachments', 'document_id')
    op.drop_table('document_attachments')
