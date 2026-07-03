"""partial_unique_constraint_part_masters

Revision ID: 6a090d6571b1
Revises: b93c9f354701
Create Date: 2026-07-02 13:00:00.000000

"""
from typing import Sequence, Union
from alembic import op

revision: str = '6a090d6571b1'
down_revision: Union[str, None] = 'b93c9f354701'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE part_masters DROP CONSTRAINT IF EXISTS uq_part_master_ws_number")
    op.execute("""
        CREATE UNIQUE INDEX uq_part_master_ws_number
        ON part_masters (workspace_id, number)
        WHERE deleted_at IS NULL
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS uq_part_master_ws_number")
    op.execute("ALTER TABLE part_masters ADD CONSTRAINT uq_part_master_ws_number UNIQUE (workspace_id, number)")
