"""add conversions table

Revision ID: 0003_add_conversions
Revises: 0002_seed_admin
Create Date: 2026-06-30

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0003_add_conversions"
down_revision: Union[str, None] = "0002_seed_admin"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "conversions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("iteration_id", sa.Uuid(), nullable=False),
        sa.Column("pending", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("succeed", sa.Boolean(), nullable=True),
        sa.Column("start_date", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("end_date", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["iteration_id"], ["part_iterations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_conversions_iteration", "conversions", ["iteration_id"])


def downgrade() -> None:
    op.drop_index("idx_conversions_iteration", table_name="conversions")
    op.drop_table("conversions")
