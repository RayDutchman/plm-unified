"""rename_component_attachments_to_part_attachments

Revision ID: aa5a019e616b
Revises: 5b1b7711d044
Create Date: 2026-06-30 20:28:51.637648

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'aa5a019e616b'
down_revision: Union[str, None] = '5b1b7711d044'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE IF EXISTS component_attachments RENAME TO part_attachments")


def downgrade() -> None:
    op.execute("ALTER TABLE IF EXISTS part_attachments RENAME TO component_attachments")
