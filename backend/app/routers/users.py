from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
import uuid

from app.database import get_db
from app.models import User
from app.crud import user as crud_user
from app.core.permissions import require_permission
from app.schemas.user import UserCreate, UserUpdate, UserResponse

router = APIRouter(prefix="/users", tags=["用户管理"])


def _resolve_workspace(user_idata, current_user):
    ws = user_idata.workspace_id
    if isinstance(ws, uuid.UUID):
        return ws
    return current_user.workspace_id


@router.get("/", response_model=list[UserResponse])
async def list_users(
    skip: int = 0, limit: int = 100,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users:read")),
):
    return crud_user.get_users(db, skip=skip, limit=limit)


@router.post("/", response_model=UserResponse)
async def create_user(
    user: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users:create")),
):
    if crud_user.get_user_by_username(db, user.username):
        raise HTTPException(status_code=400, detail="用户名已存在")
    return crud_user.create_user(
        db,
        workspace_id=_resolve_workspace(user, current_user),
        username=user.username, password=user.password,
        real_name=user.real_name, role=user.role,
        department=user.department, phone=user.phone,
    )


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users:read_detail")),
):
    db_user = crud_user.get_user(db, user_id)
    if not db_user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return db_user


@router.put("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: uuid.UUID,
    user_update: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users:update")),
):
    db_user = crud_user.update_user(db, user_id, user_update)
    if not db_user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return db_user


@router.delete("/{user_id}")
async def delete_user(
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("users:delete")),
):
    if not crud_user.delete_user(db, user_id):
        raise HTTPException(status_code=404, detail="用户不存在")
    return {"message": "用户已删除"}
