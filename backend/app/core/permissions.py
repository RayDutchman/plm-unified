"""权限矩阵校验。从 permissions/permissions.json 加载。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from fastapi import Depends, HTTPException, status

from app.models import User
from app.routers.auth import get_current_active_user

_permissions: dict[str, list[str]] = {}

def _load_permissions() -> dict[str, list[str]]:
    path = Path(__file__).parent.parent.parent / "permissions" / "permissions.json"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def require_permission(perm: str):
    """依赖注入：校验当前用户是否拥有指定权限。"""
    async def _check(current_user: User = Depends(get_current_active_user)):
        if not _permissions:
            _permissions.update(_load_permissions())
        allowed = _permissions.get(perm, [])
        if current_user.role not in allowed and "admin" not in current_user.role:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"缺少权限: {perm}")
        return current_user
    return _check
