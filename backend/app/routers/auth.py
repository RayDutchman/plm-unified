"""JWT 认证路由：登录 / 刷新 / 当前用户 / 改密。移植自 myPDM 并适配新用户表。"""
from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.crud import user as crud_user
from app.core.security import (
    create_access_token, create_refresh_token, decode_token,
    get_password_hash, verify_password,
)
from app.schemas.auth import Token, RefreshRequest, ChangePasswordRequest
from app.schemas.user import UserResponse

router = APIRouter(prefix="/auth", tags=["认证"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")


async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    try:
        payload = decode_token(token)
        username = payload.get("sub")
        # 必须是 access 令牌：拒绝用 refresh 令牌（typ=refresh）访问受保护接口，
        # 否则 7 天有效期的 refresh 令牌会沦为全 API 的长效凭证
        if not username or payload.get("typ") != "access":
            raise HTTPException(status_code=401, detail="无效的令牌")
    except JWTError:
        raise HTTPException(status_code=401, detail="令牌验证失败")
    user = crud_user.get_user_by_username(db, username)
    if not user:
        raise HTTPException(status_code=401, detail="用户不存在")
    return user


async def get_current_active_user(current_user: User = Depends(get_current_user)) -> User:
    if current_user.status != "active":
        raise HTTPException(status_code=403, detail="账户已被禁用")
    return current_user


def require_role(roles):
    async def checker(current_user: User = Depends(get_current_active_user)) -> User:
        if current_user.role not in roles:
            raise HTTPException(status_code=403, detail="权限不足")
        return current_user
    return checker


def _issue_tokens(user: User) -> Token:
    claims = {"sub": user.username, "role": user.role, "workspace_id": str(user.workspace_id)}
    return Token(
        access_token=create_access_token(claims),
        refresh_token=create_refresh_token(user.username),
        token_type="bearer",
    )


@router.post("/token", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = crud_user.authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="用户名或密码错误", headers={"WWW-Authenticate": "Bearer"})
    return _issue_tokens(user)


@router.post("/refresh", response_model=Token)
async def refresh(req: RefreshRequest, db: Session = Depends(get_db)):
    try:
        payload = decode_token(req.refresh_token)
        if payload.get("typ") != "refresh":
            raise HTTPException(status_code=401, detail="无效的刷新令牌")
        username = payload.get("sub")
    except JWTError:
        raise HTTPException(status_code=401, detail="刷新令牌验证失败")
    user = crud_user.get_user_by_username(db, username)
    if not user or user.status != "active":
        raise HTTPException(status_code=401, detail="用户不可用")
    return _issue_tokens(user)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: User = Depends(get_current_active_user)):
    return current_user


@router.post("/change-password")
async def change_password(req: ChangePasswordRequest,
                          current_user: User = Depends(get_current_active_user),
                          db: Session = Depends(get_db)):
    if not verify_password(req.old_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="原密码错误")
    current_user.password_hash = get_password_hash(req.new_password)
    db.commit()
    return {"message": "密码修改成功"}
