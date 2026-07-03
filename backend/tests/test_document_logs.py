"""图文档操作记录相关测试。"""
from app.crud import get_logs
from app.models import OperationLog


def test_get_logs_supports_multiple_target_types(db):
    """get_logs 应支持传入 target_type 列表同时过滤多种类型。"""
    from app.models import Workspace, User
    from app.core.security import get_password_hash
    ws = Workspace(name="w")
    db.add(ws)
    db.commit()
    db.refresh(ws)
    u = User(workspace_id=ws.id, username="admin", password_hash=get_password_hash("x"), real_name="A", role="admin")
    db.add(u)
    db.commit()

    log1 = OperationLog(user_id=u.id, username="admin", action="创建图文档", target_type="document", target_id="doc-1")
    log2 = OperationLog(user_id=u.id, username="admin", action="上传附件", target_type="document_att", target_id="doc-1")
    log3 = OperationLog(user_id=u.id, username="admin", action="更新图文档", target_type="document", target_id="doc-2")
    db.add_all([log1, log2, log3])
    db.commit()

    items, total = get_logs(db, target_type=["document", "document_att"], target_id="doc-1")
    assert total == 2
    actions = {log.action for log in items}
    assert actions == {"创建图文档", "上传附件"}

    # 旧参数类型兼容性断言
    items, total = get_logs(db, target_type="document", target_id="doc-1")
    assert total == 1
    assert items[0].action == "创建图文档"

    items, total = get_logs(db, target_id="doc-1")
    assert total == 2


import pytest
import uuid
from fastapi.testclient import TestClient


@pytest.fixture
def client_with_logs(db):
    from app.main import app
    from app.database import get_db
    from app.models import Workspace, User, Document, UserGroup
    from app.core.security import get_password_hash
    from app.crud import create_log

    ws = Workspace(name="w")
    db.add(ws)
    db.commit()
    db.refresh(ws)

    admin = User(workspace_id=ws.id, username="admin", password_hash=get_password_hash("admin12345"),
                 real_name="管理员", role="admin")
    viewer = User(workspace_id=ws.id, username="viewer", password_hash=get_password_hash("viewer123"),
                  real_name="查看者", role="user")
    db.add_all([admin, viewer])
    db.commit()
    db.refresh(admin)
    db.refresh(viewer)

    doc = Document(code="DOC-001", name="测试图文档", version="A", status="draft", creator_id=admin.id)
    db.add(doc)
    db.commit()
    db.refresh(doc)

    group_doc = Document(code="DOC-002", name="受控图文档", version="A", status="draft", creator_id=admin.id)
    db.add(group_doc)
    db.commit()
    db.refresh(group_doc)
    g = UserGroup(name="g1")
    db.add(g)
    db.commit()
    db.refresh(g)
    from app.models.models_document import DocumentGroupLink
    db.add(DocumentGroupLink(document_id=group_doc.id, group_id=g.id))
    db.commit()

    create_log(db, admin.id, admin.username, "创建图文档", "document", str(doc.id), "编号:DOC-001", None)
    create_log(db, admin.id, admin.username, "上传附件", "document_att", str(doc.id), "文件:1.pdf", None)

    def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app), admin, viewer, doc, group_doc
    finally:
        app.dependency_overrides.clear()


def test_list_document_logs_success(client_with_logs):
    client, admin, viewer, doc, group_doc = client_with_logs
    r = client.post("/api/auth/token", data={"username": "admin", "password": "admin12345"})
    token = r.json()["access_token"]

    res = client.get(f"/api/documents/{doc.id}/logs", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    body = res.json()
    assert body["total"] == 2
    actions = {item["action"] for item in body["items"]}
    assert actions == {"创建图文档", "上传附件"}


def test_list_document_logs_forbidden_for_unauthorized_role(client_with_logs):
    client, admin, viewer, doc, group_doc = client_with_logs
    # 使用未在权限表中授权的角色验证权限拦截
    r = client.post("/api/auth/token", data={"username": "viewer", "password": "viewer123"})
    assert r.status_code == 200, r.text
    token = r.json()["access_token"]

    res = client.get(f"/api/documents/{doc.id}/logs", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403


def test_list_document_logs_group_access_denied(client_with_logs):
    client, admin, viewer, doc, group_doc = client_with_logs
    r = client.post("/api/auth/token", data={"username": "viewer", "password": "viewer123"})
    token = r.json()["access_token"]

    # viewer 不在 group_doc 的关联用户组中，应 403
    res = client.get(f"/api/documents/{group_doc.id}/logs", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403


def test_list_document_logs_not_found(client_with_logs):
    client, admin, viewer, doc, group_doc = client_with_logs
    r = client.post("/api/auth/token", data={"username": "admin", "password": "admin12345"})
    token = r.json()["access_token"]

    res = client.get(f"/api/documents/{uuid.uuid4()}/logs", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 404


def test_list_document_logs_empty(client_with_logs):
    client, admin, viewer, doc, group_doc = client_with_logs
    r = client.post("/api/auth/token", data={"username": "admin", "password": "admin12345"})
    token = r.json()["access_token"]

    res = client.get(f"/api/documents/{group_doc.id}/logs", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200
    assert res.json() == {"items": [], "total": 0}
