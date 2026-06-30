"""用户读取与认证。"""
from sqlalchemy.orm import Session

from app.models import User
from app.core.security import verify_password, get_password_hash


def get_user_by_username(db: Session, username: str) -> User | None:
    return (
        db.query(User)
        .filter(User.username == username, User.deleted_at.is_(None))
        .first()
    )


def get_user(db: Session, user_id) -> User | None:
    return (
        db.query(User)
        .filter(User.id == user_id, User.deleted_at.is_(None))
        .first()
    )


def get_users(db: Session, skip: int = 0, limit: int = 100) -> list[User]:
    return (
        db.query(User)
        .filter(User.deleted_at.is_(None))
        .offset(skip).limit(limit).all()
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


def update_user(db: Session, user_id, user_update) -> User | None:
    db_user = get_user(db, user_id)
    if not db_user:
        return None
    update_data = user_update.model_dump(exclude_unset=True)
    if "password" in update_data:
        update_data["password_hash"] = get_password_hash(update_data.pop("password"))
    for field, value in update_data.items():
        setattr(db_user, field, value)
    db.commit()
    db.refresh(db_user)
    return db_user


def delete_user(db: Session, user_id) -> User | None:
    db_user = get_user(db, user_id)
    if db_user:
        db.delete(db_user)
        db.commit()
    return db_user
