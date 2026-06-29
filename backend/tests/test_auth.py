"""M1.5 认证测试。"""
import pytest
from jose import ExpiredSignatureError


def test_password_hash_roundtrip():
    from app.core.security import get_password_hash, verify_password
    h = get_password_hash("admin12345")
    assert h != "admin12345"
    assert verify_password("admin12345", h) is True
    assert verify_password("wrong", h) is False


def test_verify_password_handles_garbage_hash():
    from app.core.security import verify_password
    assert verify_password("x", "not-a-bcrypt-hash") is False


def test_access_token_encode_decode():
    from app.core.security import create_access_token, decode_token
    tok = create_access_token({"sub": "admin", "role": "admin"})
    payload = decode_token(tok)
    assert payload["sub"] == "admin"
    assert payload["role"] == "admin"
    assert payload["typ"] == "access"


def test_expired_token_rejected():
    from datetime import timedelta
    from app.core.security import create_access_token, decode_token
    tok = create_access_token({"sub": "admin"}, expires_delta=timedelta(seconds=-1))
    with pytest.raises(ExpiredSignatureError):
        decode_token(tok)


def _seed_user(db, username="admin", password="admin12345", role="admin", status="active"):
    from app.models import Workspace, User
    from app.core.security import get_password_hash
    ws = Workspace(name="w"); db.add(ws); db.commit(); db.refresh(ws)
    u = User(workspace_id=ws.id, username=username, password_hash=get_password_hash(password),
             real_name="管理员", role=role, status=status)
    db.add(u); db.commit(); db.refresh(u)
    return u


def test_get_user_by_username(db):
    from app.crud import user as crud_user
    _seed_user(db)
    assert crud_user.get_user_by_username(db, "admin").username == "admin"
    assert crud_user.get_user_by_username(db, "nobody") is None


def test_authenticate_user(db):
    from app.crud import user as crud_user
    _seed_user(db)
    assert crud_user.authenticate_user(db, "admin", "admin12345") is not None
    assert crud_user.authenticate_user(db, "admin", "wrong") is None
    assert crud_user.authenticate_user(db, "nobody", "x") is None


def test_authenticate_ignores_soft_deleted(db):
    from app.crud import user as crud_user
    u = _seed_user(db)
    from datetime import datetime
    u.deleted_at = datetime.utcnow(); db.commit()
    assert crud_user.get_user_by_username(db, "admin") is None
