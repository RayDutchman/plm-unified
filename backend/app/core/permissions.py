"""权限矩阵校验。权限映射来自随代码打包的 app/permissions/_generated.py。"""
from __future__ import annotations

from typing import Optional

from fastapi import Depends, HTTPException, status

from app.models import User
from app.routers.auth import get_current_active_user

_permissions: dict[str, list[str]] = {}
_OBJECT_POLICY_FUNCS: dict = {}

def _load_permissions() -> dict[str, list[str]]:
    # 权限矩阵由 tools/gen_permissions.py 生成到 app/permissions/_generated.py，
    # 随 app 目录一起打进镜像、始终存在；不再读取 app 目录外的 permissions.json
    # （该文件不会被 Docker COPY 进镜像，导致容器内加载为空、非 admin 用户全被 403）。
    from app.permissions._generated import PERMISSIONS
    return dict(PERMISSIONS)


def register_policy(name: str):
    def deco(fn):
        _OBJECT_POLICY_FUNCS[name] = fn
        return fn
    return deco


def check_object_policy(name: str, user: User, obj, **ctx) -> bool:
    fn = _OBJECT_POLICY_FUNCS.get(name)
    if fn is None:
        raise KeyError(f"Unregistered object policy: {name}")
    return bool(fn(user, obj, **ctx))


def enforce_object_policy(name: str, user: User, obj, **ctx) -> None:
    if not check_object_policy(name, user, obj, **ctx):
        raise HTTPException(status_code=403, detail="无权操作该对象")


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


def _is_admin(user) -> bool:
    return user.role == "admin"


@register_policy("project_manager_or_admin")
def _project_manager_or_admin(user, project, **_) -> bool:
    return _is_admin(user) or getattr(project, "owner_id", None) == user.id


@register_policy("ecr_owner_or_admin")
def _ecr_owner_or_admin(user, ecr, **_) -> bool:
    return _is_admin(user) or getattr(ecr, "creator_id", None) == user.id


@register_policy("eco_owner_or_admin")
def _eco_owner_or_admin(user, eco, **_) -> bool:
    return _is_admin(user) or getattr(eco, "creator_id", None) == user.id


@register_policy("ecr_approver_or_admin")
def _ecr_approver_or_admin(user, ecr, *, reviewer_ids=None, **_) -> bool:
    return _is_admin(user) or (reviewer_ids is not None and user.id in reviewer_ids)


@register_policy("dashboard_folder_editor")
def _dashboard_folder_editor(user, folder, **_) -> bool:
    if _is_admin(user) or getattr(folder, "owner_user_id", None) == user.id:
        return True
    for share in getattr(folder, "shares", []) or []:
        if share.shared_with_user_id == user.id and share.permission == "edit":
            return True
    return False


@register_policy("inventory_keeper_or_admin")
def _inventory_keeper_or_admin(user, doc, **_) -> bool:
    return _is_admin(user) or getattr(doc, "keeper_id", None) == user.id


@register_policy("document_content_access")
def _document_content_access(user, document, *, user_group_ids=frozenset(), doc_group_ids=frozenset(), **_) -> bool:
    if _is_admin(user):
        return True
    if getattr(document, "creator_id", None) == user.id:
        return True
    if not doc_group_ids:
        return True
    return bool(set(user_group_ids) & set(doc_group_ids))
