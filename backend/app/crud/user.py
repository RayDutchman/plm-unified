"""用户读取与认证。"""
from sqlalchemy.orm import Session

from app.models import User
from app.core.security import verify_password, get_password_hash


def get_user_by_username(db: Session, username: str) -> User | None:
    # 软删除用户视为不存在
    return (
        db.query(User)
        .filter(User.username == username, User.deleted_at.is_(None))
        .first()
    )


def authenticate_user(db: Session, username: str, password: str) -> User | None:
    user = get_user_by_username(db, username)
    if not user or not verify_password(password, user.password_hash):
        return None
    return user


def create_user(db: Session, *, workspace_id, username, password, real_name,
                role, department=None, phone=None, status="active") -> User:
    user = User(
        workspace_id=workspace_id, username=username,
        password_hash=get_password_hash(password), real_name=real_name,
        role=role, department=department, phone=phone, status=status,
    )
    db.add(user); db.commit(); db.refresh(user)
    return user
