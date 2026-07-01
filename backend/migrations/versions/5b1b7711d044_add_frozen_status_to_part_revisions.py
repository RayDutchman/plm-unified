"""add_frozen_status_to_part_revisions

Revision ID: 5b1b7711d044
Revises: ba16aed1bc01
Create Date: 2026-06-30 19:56:13.964285

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '5b1b7711d044'
down_revision: Union[str, None] = 'ba16aed1bc01'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE part_revisions DROP CONSTRAINT IF EXISTS ck_part_revision_status")
    op.execute("ALTER TABLE part_revisions ADD CONSTRAINT ck_part_revision_status CHECK (status IN ('WIP','FROZEN','RELEASED','OBSOLETE'))")


def downgrade() -> None:
    op.execute("ALTER TABLE part_revisions DROP CONSTRAINT IF EXISTS ck_part_revision_status")
    op.execute("ALTER TABLE part_revisions ADD CONSTRAINT ck_part_revision_status CHECK (status IN ('WIP','RELEASED','OBSOLETE'))")
