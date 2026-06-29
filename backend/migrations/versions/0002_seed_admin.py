"""seed admin user

Revision ID: 0002_seed_admin
Revises: 0001_initial_schema
Create Date: 2026-06-29

"""
from typing import Sequence, Union

from alembic import op

revision: str = "0002_seed_admin"
down_revision: Union[str, None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# 默认工作空间 id（迁移 0001 已插入）
_DEFAULT_WS = "00000000-0000-0000-0000-000000000001"
_ADMIN_ID = "00000000-0000-0000-0000-000000000010"
# admin12345 的 bcrypt 哈希（开发种子，首次登录后请改密）
_ADMIN_HASH = "$2b$12$StQrQwZUxi9mQ1fakoSJpeFOpo0G.UQ8VU8YINxQ2fEe2KlCbJ.7."


def upgrade() -> None:
    op.execute(
        "INSERT INTO users (id, workspace_id, username, password_hash, real_name, role, status, created_at, updated_at) "
        f"VALUES ('{_ADMIN_ID}', '{_DEFAULT_WS}', 'admin', '{_ADMIN_HASH}', '系统管理员', 'admin', 'active', now(), now())"
    )


def downgrade() -> None:
    op.execute(f"DELETE FROM users WHERE id = '{_ADMIN_ID}'")
