"""seed admin user

Revision ID: 0002_seed_admin
Revises: 0001_initial_schema
Create Date: 2026-06-29

"""
from typing import Sequence, Union

import sqlalchemy as sa
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
    # 用绑定参数而非 f-string 拼接，避免 SQL 注入模式扩散
    op.execute(
        sa.text(
            "INSERT INTO users (id, workspace_id, username, password_hash, real_name, role, status, created_at, updated_at) "
            "VALUES (:id, :ws, :username, :pwd, :real_name, :role, :status, now(), now())"
        ).bindparams(
            id=_ADMIN_ID, ws=_DEFAULT_WS, username="admin", pwd=_ADMIN_HASH,
            real_name="系统管理员", role="admin", status="active",
        )
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM users WHERE id = :id").bindparams(id=_ADMIN_ID))
