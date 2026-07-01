from app.permissions._generated import PERMISSIONS, ROLES, OBJECT_POLICIES
from app.permissions.policies import enforce_object_policy, register_policy, check_object_policy
from app.models import User


def has_permission(user: User, perm: str) -> bool:
    allowed = PERMISSIONS.get(perm, [])
    return user.role in allowed or user.role == "admin"


def require_permission(perm: str):
    from fastapi import Depends, HTTPException
    from app.routers.auth import get_current_active_user

    async def checker(current_user: User = Depends(get_current_active_user)) -> User:
        allowed = PERMISSIONS.get(perm, [])
        if current_user.role not in allowed and current_user.role != "admin":
            raise HTTPException(status_code=403, detail="权限不足")
        return current_user
    return checker
