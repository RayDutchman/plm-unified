"""M1 数据地基：模型与约束测试（SQLite 内存库）。"""


def test_database_module_exposes_base_and_get_db():
    from app.database import Base, get_db, SessionLocal
    assert Base is not None
    assert callable(get_db)
    assert SessionLocal is not None


import uuid
import pytest
from sqlalchemy.exc import IntegrityError


def test_workspace_and_user_roundtrip(db):
    from app.models import Workspace, User
    ws = Workspace(name="default")
    db.add(ws); db.commit(); db.refresh(ws)
    assert isinstance(ws.id, uuid.UUID)

    user = User(
        workspace_id=ws.id, username="admin", password_hash="x",
        real_name="管理员", role="admin", status="active",
    )
    db.add(user); db.commit(); db.refresh(user)
    assert user.created_at is not None
    assert user.deleted_at is None


def test_user_username_unique(db):
    from app.models import Workspace, User
    ws = Workspace(name="w"); db.add(ws); db.commit()
    db.add(User(workspace_id=ws.id, username="dup", password_hash="x",
                real_name="a", role="admin", status="active"))
    db.commit()
    db.add(User(workspace_id=ws.id, username="dup", password_hash="x",
                real_name="b", role="admin", status="active"))
    with pytest.raises(IntegrityError):
        db.commit()
