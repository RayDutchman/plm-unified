"""create_part_attachments_table

Revision ID: 566ea1d2c5de
Revises: aa5a019e616b
Create Date: 2026-06-30 20:54:00.964303

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '566ea1d2c5de'
down_revision: Union[str, None] = 'aa5a019e616b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('part_attachments',
    sa.Column('id', sa.Uuid(), nullable=False),
    sa.Column('part_master_id', sa.Uuid(), nullable=False),
    sa.Column('category', sa.String(length=32), nullable=False),
    sa.Column('file_name', sa.String(length=255), nullable=True),
    sa.Column('file_size', sa.Integer(), nullable=True),
    sa.Column('file_path', sa.String(length=512), nullable=True),
    sa.Column('file_hash', sa.String(length=64), nullable=True),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
    sa.ForeignKeyConstraint(['part_master_id'], ['part_masters.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )


def downgrade() -> None:
    op.drop_table('part_attachments')
