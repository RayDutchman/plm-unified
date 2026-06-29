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


def test_user_response_from_orm(db):
    from app.schemas.user import UserResponse
    u = _seed_user(db)
    resp = UserResponse.model_validate(u)
    assert resp.username == "admin"
    assert resp.workspace_id == u.workspace_id
    assert not hasattr(resp, "password_hash")


def test_token_schema_defaults():
    from app.schemas.auth import Token
    t = Token(access_token="a")
    assert t.token_type == "bearer"
    assert t.refresh_token is None


from fastapi.testclient import TestClient


@pytest.fixture
def client(db):
    from app.main import app
    from app.database import get_db
    _seed_user(db, username="admin", password="admin12345")

    def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def test_login_success_and_me(client):
    r = client.post("/api/auth/token", data={"username": "admin", "password": "admin12345"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["token_type"] == "bearer"
    token = body["access_token"]

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["username"] == "admin"


def test_login_wrong_password_401(client):
    r = client.post("/api/auth/token", data={"username": "admin", "password": "nope"})
    assert r.status_code == 401


def test_me_without_token_401(client):
    assert client.get("/api/auth/me").status_code == 401


def test_refresh_flow(client):
    r = client.post("/api/auth/token", data={"username": "admin", "password": "admin12345"})
    refresh_token = r.json()["refresh_token"]
    r2 = client.post("/api/auth/refresh", json={"refresh_token": refresh_token})
    assert r2.status_code == 200
    assert r2.json()["access_token"]


def test_change_password(client):
    r = client.post("/api/auth/token", data={"username": "admin", "password": "admin12345"})
    token = r.json()["access_token"]
    r2 = client.post("/api/auth/change-password",
                     headers={"Authorization": f"Bearer {token}"},
                     json={"old_password": "admin12345", "new_password": "newpass123"})
    assert r2.status_code == 200
    # 旧密码失效、新密码可登录
    assert client.post("/api/auth/token", data={"username": "admin", "password": "admin12345"}).status_code == 401
    assert client.post("/api/auth/token", data={"username": "admin", "password": "newpass123"}).status_code == 200


def test_refresh_token_rejected_at_protected_endpoint(client):
    # refresh 令牌不得当作 access 令牌访问受保护接口（typ 必须为 access）
    r = client.post("/api/auth/token", data={"username": "admin", "password": "admin12345"})
    refresh_token = r.json()["refresh_token"]
    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {refresh_token}"})
    assert me.status_code == 401


def test_access_token_rejected_at_refresh(client):
    # access 令牌不得用于刷新（/refresh 要求 typ=refresh）
    r = client.post("/api/auth/token", data={"username": "admin", "password": "admin12345"})
    access_token = r.json()["access_token"]
    r2 = client.post("/api/auth/refresh", json={"refresh_token": access_token})
    assert r2.status_code == 401


def test_forged_token_rejected_at_me(client):
    # 伪造/格式错误的令牌经 HTTP 层应 401
    me = client.get("/api/auth/me", headers={"Authorization": "Bearer not.a.valid.token"})
    assert me.status_code == 401
