"""
M1 验收测试。

覆盖 milestones.md M1 验收条件：
  能通过 API 创建零件、签出、修改、签入，
  签出状态被第二个用户请求时返回 409，数据正确写入库。

流程（严格对应 1.9 要求）：
  1. 种子：admin + user_b 两个账号，默认 workspace
  2. admin 登录，获取 JWT
  3. 创建零件 P-001 → 断言 Revision A / Iteration 1 自动生成
  4. admin checkout A → 断言 checkoutUserId 被置位
  5. user_b 尝试 checkout A → 断言 409
  6. admin checkin A → 断言生成 Iteration 2，Iteration 1 冻结
  7. admin 发起新一轮 checkout → checkin 获得 Iteration 3 → undocheckout
     → 断言草稿 Iteration 3 被丢弃
  8. 校验数据库落库正确（直接查 DB）
"""
import uuid

import pytest
from fastapi.testclient import TestClient

from app.core.security import get_password_hash
from app.database import get_db
from app.main import app
from app.models import User, Workspace
from app.models.part import PartIteration, PartMaster, PartRevision


# ---------------------------------------------------------------------------
# 常量：默认 workspace（与 Alembic 迁移种子一致）
# ---------------------------------------------------------------------------
_WS_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
_ADMIN_ID = uuid.UUID("00000000-0000-0000-0000-000000000010")
_USER_B_ID = uuid.UUID("00000000-0000-0000-0000-000000000020")


# ---------------------------------------------------------------------------
# Fixture：HTTP 客户端，覆盖 get_db 依赖注入，每次测试独立 DB
# ---------------------------------------------------------------------------

@pytest.fixture
def client(db):
    """
    返回 TestClient，并将 FastAPI 的 get_db 依赖重定向到测试用 SQLite 内存库。
    每次测试结束后清理 dependency_overrides，防止测试间污染。
    """
    # 种子：workspace
    ws = Workspace(id=_WS_ID, name="default")
    db.add(ws)
    db.flush()

    # 种子：admin 用户
    admin = User(
        id=_ADMIN_ID,
        workspace_id=_WS_ID,
        username="admin",
        password_hash=get_password_hash("admin12345"),
        real_name="管理员",
        role="admin",
        status="active",
    )
    # 种子：user_b 用户
    user_b = User(
        id=_USER_B_ID,
        workspace_id=_WS_ID,
        username="user_b",
        password_hash=get_password_hash("pass12345"),
        real_name="用户B",
        role="engineer",
        status="active",
    )
    db.add_all([admin, user_b])
    db.commit()

    def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# 辅助：登录并返回 Bearer 头
# ---------------------------------------------------------------------------

def _login(client: TestClient, username: str, password: str) -> dict:
    r = client.post("/api/auth/token", data={"username": username, "password": password})
    assert r.status_code == 200, f"登录失败: {r.text}"
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# ---------------------------------------------------------------------------
# 1.9 M1 验收测试
# ---------------------------------------------------------------------------

class TestM1Acceptance:
    """
    M1 完整业务流验收。
    测试按顺序在同一 db 实例内执行（每个方法共享 client fixture 的 db）。
    """

    def test_01_login(self, client):
        """admin 能正常登录并获取 access_token。"""
        headers = _login(client, "admin", "admin12345")
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Bearer ")

    def test_02_create_part_auto_generates_three_layers(self, client, db):
        """
        创建零件时自动生成：
          - PartRevision version=A, status=WIP
          - PartIteration iteration=1, checkInDate=null
          - 创建者自动签出（checkoutUserId 非空）
        """
        headers = _login(client, "admin", "admin12345")
        r = client.post("/api/parts", json={
            "number": "P-001",
            "name": "主验收零件",
            "workspaceId": str(_WS_ID),
        }, headers=headers)
        assert r.status_code == 201, r.text
        body = r.json()

        # 顶层字段
        assert body["number"] == "P-001"
        assert body["workspaceId"] == str(_WS_ID)

        # 版本层
        assert len(body["revisions"]) == 1
        rev = body["revisions"][0]
        assert rev["version"] == "A"
        assert rev["status"] == "WIP"
        assert rev["checkoutUserId"] == str(_ADMIN_ID)  # 自动签出给创建者
        assert rev["checkoutDate"] is not None

        # 迭代层
        assert len(rev["iterations"]) == 1
        itr = rev["iterations"][0]
        assert itr["iteration"] == 1
        assert itr["checkInDate"] is None  # 未签入

        # 数据库层校验
        master = db.query(PartMaster).filter_by(number="P-001").first()
        assert master is not None
        revision = db.query(PartRevision).filter_by(part_master_id=master.id).first()
        assert revision.checkout_user_id == _ADMIN_ID
        iteration = db.query(PartIteration).filter_by(part_revision_id=revision.id).first()
        assert iteration.iteration == 1
        assert iteration.check_in_date is None

    def test_03_admin_already_checked_out_second_checkout_fails_409(self, client):
        """
        admin 创建后自动持有签出锁，第二次签出（同用户）应 409。
        验证：任何用户（包括签出者本人）在持锁时不能重复签出。
        """
        headers = _login(client, "admin", "admin12345")
        client.post("/api/parts", json={
            "number": "P-001", "name": "测试件", "workspaceId": str(_WS_ID),
        }, headers=headers)

        # admin 自己再签出 → 409（已签出）
        r = client.put(
            f"/api/parts/P-001/A/checkout?workspace_id={_WS_ID}",
            headers=headers,
        )
        assert r.status_code == 409, r.text

    def test_04_user_b_checkout_while_admin_holds_lock_returns_409(self, client):
        """
        user_b 在 admin 持锁期间签出 → 409（核心并发保护验收）。
        """
        admin_h = _login(client, "admin", "admin12345")
        user_b_h = _login(client, "user_b", "pass12345")

        # admin 创建（自动签出）
        client.post("/api/parts", json={
            "number": "P-001", "name": "测试件", "workspaceId": str(_WS_ID),
        }, headers=admin_h)

        # user_b 尝试签出 → 409
        r = client.put(
            f"/api/parts/P-001/A/checkout?workspace_id={_WS_ID}",
            headers=user_b_h,
        )
        assert r.status_code == 409, r.text
        assert "签出" in r.json()["detail"]

    def test_05_checkin_freezes_iteration_and_creates_next(self, client, db):
        """
        admin 签入：
          - Iteration 1 的 checkInDate 非空（冻结）
          - 自动生成 Iteration 2，checkInDate=null
          - 版本签出锁清除（checkoutUserId=null）
        """
        headers = _login(client, "admin", "admin12345")
        client.post("/api/parts", json={
            "number": "P-001", "name": "测试件", "workspaceId": str(_WS_ID),
        }, headers=headers)

        r = client.put(
            f"/api/parts/P-001/A/checkin?workspace_id={_WS_ID}&iteration_note=首次签入",
            headers=headers,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["checkoutUserId"] is None
        assert body["checkoutDate"] is None

        # 数据库校验
        master = db.query(PartMaster).filter_by(number="P-001").first()
        revision = db.query(PartRevision).filter_by(part_master_id=master.id).first()
        db.refresh(revision)
        assert revision.checkout_user_id is None

        iters = (
            db.query(PartIteration)
            .filter_by(part_revision_id=revision.id)
            .order_by(PartIteration.iteration)
            .all()
        )
        assert len(iters) == 2

        assert iters[0].iteration == 1
        assert iters[0].check_in_date is not None          # 已冻结
        assert iters[0].iteration_note == "首次签入"       # 备注写入

        assert iters[1].iteration == 2
        assert iters[1].check_in_date is None              # 新草稿未冻结

    def test_06_after_checkin_user_b_can_checkout(self, client):
        """
        admin 签入释放锁后，user_b 可以成功签出。
        """
        admin_h = _login(client, "admin", "admin12345")
        user_b_h = _login(client, "user_b", "pass12345")

        client.post("/api/parts", json={
            "number": "P-001", "name": "测试件", "workspaceId": str(_WS_ID),
        }, headers=admin_h)
        client.put(f"/api/parts/P-001/A/checkin?workspace_id={_WS_ID}", headers=admin_h)

        r = client.put(
            f"/api/parts/P-001/A/checkout?workspace_id={_WS_ID}",
            headers=user_b_h,
        )
        assert r.status_code == 200, r.text
        assert r.json()["checkoutUserId"] == str(_USER_B_ID)

    def test_07_undocheckout_discards_draft_iteration(self, client, db):
        """
        撤销签出（iteration > 1）时草稿迭代被删除。

        流程：创建 → 签入（生成 iter2）→ 签出 → 撤销签出
        断言：iter2 被删除，只剩 iter1（已冻结）
        """
        headers = _login(client, "admin", "admin12345")
        client.post("/api/parts", json={
            "number": "P-001", "name": "测试件", "workspaceId": str(_WS_ID),
        }, headers=headers)
        client.put(f"/api/parts/P-001/A/checkin?workspace_id={_WS_ID}", headers=headers)
        client.put(f"/api/parts/P-001/A/checkout?workspace_id={_WS_ID}", headers=headers)

        r = client.put(
            f"/api/parts/P-001/A/undocheckout?workspace_id={_WS_ID}",
            headers=headers,
        )
        assert r.status_code == 200, r.text
        assert r.json()["checkoutUserId"] is None

        # 数据库：只剩 iter1（iter2 草稿已删）
        master = db.query(PartMaster).filter_by(number="P-001").first()
        revision = db.query(PartRevision).filter_by(part_master_id=master.id).first()
        iters = (
            db.query(PartIteration)
            .filter_by(part_revision_id=revision.id)
            .order_by(PartIteration.iteration)
            .all()
        )
        assert len(iters) == 1
        assert iters[0].iteration == 1
        assert iters[0].check_in_date is not None  # iter1 仍然冻结

    def test_08_non_owner_cannot_checkin_409(self, client):
        """非签出本人签入 → 409。"""
        admin_h = _login(client, "admin", "admin12345")
        user_b_h = _login(client, "user_b", "pass12345")

        client.post("/api/parts", json={
            "number": "P-001", "name": "测试件", "workspaceId": str(_WS_ID),
        }, headers=admin_h)

        # user_b 尝试签入 admin 持有的锁 → 409
        r = client.put(
            f"/api/parts/P-001/A/checkin?workspace_id={_WS_ID}",
            headers=user_b_h,
        )
        assert r.status_code == 409, r.text

    def test_09_non_owner_cannot_undocheckout_409(self, client):
        """非签出本人撤销签出 → 409。"""
        admin_h = _login(client, "admin", "admin12345")
        user_b_h = _login(client, "user_b", "pass12345")

        client.post("/api/parts", json={
            "number": "P-001", "name": "测试件", "workspaceId": str(_WS_ID),
        }, headers=admin_h)

        r = client.put(
            f"/api/parts/P-001/A/undocheckout?workspace_id={_WS_ID}",
            headers=user_b_h,
        )
        assert r.status_code == 409, r.text

    def test_10_get_part_returns_full_structure(self, client):
        """
        GET /api/parts/{number} 返回完整结构：
        含 revisions + iterations，字段为 camelCase。
        """
        headers = _login(client, "admin", "admin12345")
        client.post("/api/parts", json={
            "number": "P-001", "name": "主轴零件", "workspaceId": str(_WS_ID),
        }, headers=headers)
        client.put(f"/api/parts/P-001/A/checkin?workspace_id={_WS_ID}", headers=headers)

        r = client.get(f"/api/parts/P-001?workspace_id={_WS_ID}", headers=headers)
        assert r.status_code == 200, r.text
        body = r.json()

        assert body["number"] == "P-001"
        assert body["name"] == "主轴零件"
        # camelCase 字段名校验
        assert "workspaceId" in body
        assert "authorId" in body
        assert "createdAt" in body
        assert "updatedAt" in body

        rev = body["revisions"][0]
        assert "checkoutUserId" in rev
        assert "checkoutDate" in rev

        assert len(rev["iterations"]) == 2
        assert rev["iterations"][0]["checkInDate"] is not None   # iter1 冻结
        assert rev["iterations"][1]["checkInDate"] is None       # iter2 草稿

    def test_11_list_parts_returns_latest_status(self, client):
        """
        GET /api/parts 列表中包含最新版本的签出状态。
        """
        headers = _login(client, "admin", "admin12345")
        for i in range(3):
            client.post("/api/parts", json={
                "number": f"P-{i:03d}",
                "name": f"零件{i}",
                "workspaceId": str(_WS_ID),
            }, headers=headers)

        r = client.get(f"/api/parts?workspace_id={_WS_ID}", headers=headers)
        assert r.status_code == 200, r.text
        items = r.json()
        assert len(items) == 3

        # camelCase 字段存在
        for item in items:
            assert "latestVersion" in item
            assert "latestStatus" in item
            assert "checkoutUserId" in item

    def test_12_duplicate_number_returns_409(self, client):
        """同工作空间重复编号 → 409。"""
        headers = _login(client, "admin", "admin12345")
        payload = {"number": "P-DUP", "name": "重复件", "workspaceId": str(_WS_ID)}
        assert client.post("/api/parts", json=payload, headers=headers).status_code == 201
        r = client.post("/api/parts", json=payload, headers=headers)
        assert r.status_code == 409, r.text

    def test_13_get_nonexistent_part_returns_404(self, client):
        """查询不存在的零件 → 404。"""
        headers = _login(client, "admin", "admin12345")
        r = client.get(f"/api/parts/NONEXISTENT?workspace_id={_WS_ID}", headers=headers)
        assert r.status_code == 404, r.text

    def test_14_unauthenticated_request_returns_401(self, client):
        """无 token 访问受保护接口 → 401。"""
        r = client.get(f"/api/parts?workspace_id={_WS_ID}")
        assert r.status_code == 401, r.text

    def test_15_full_flow_data_integrity(self, client, db):
        """
        完整流程数据一致性校验：
          创建 → 签入 → 签出(user_b) → 签入(user_b)
          最终验证：3 个 iteration，iter1/2 冻结，iter3 草稿，签出锁清空
        """
        admin_h = _login(client, "admin", "admin12345")
        user_b_h = _login(client, "user_b", "pass12345")

        # Step 1：admin 创建（自动签出 iter1）
        client.post("/api/parts", json={
            "number": "P-FLOW", "name": "流程验证件", "workspaceId": str(_WS_ID),
        }, headers=admin_h)

        # Step 2：admin 签入（冻结 iter1，生成 iter2）
        client.put(f"/api/parts/P-FLOW/A/checkin?workspace_id={_WS_ID}", headers=admin_h)

        # Step 3：user_b 签出（获取 iter2 的编辑权）
        r = client.put(f"/api/parts/P-FLOW/A/checkout?workspace_id={_WS_ID}", headers=user_b_h)
        assert r.status_code == 200

        # Step 4：admin 尝试签出 → 409（user_b 持锁）
        r = client.put(f"/api/parts/P-FLOW/A/checkout?workspace_id={_WS_ID}", headers=admin_h)
        assert r.status_code == 409

        # Step 5：user_b 签入（冻结 iter2，生成 iter3）
        client.put(f"/api/parts/P-FLOW/A/checkin?workspace_id={_WS_ID}", headers=user_b_h)

        # 数据库最终状态校验
        master = db.query(PartMaster).filter_by(number="P-FLOW").first()
        revision = db.query(PartRevision).filter_by(part_master_id=master.id).first()
        db.refresh(revision)

        assert revision.checkout_user_id is None
        assert revision.checkout_date is None

        iters = (
            db.query(PartIteration)
            .filter_by(part_revision_id=revision.id)
            .order_by(PartIteration.iteration)
            .all()
        )
        assert len(iters) == 3
        assert iters[0].check_in_date is not None   # iter1 冻结（admin 签入）
        assert iters[1].check_in_date is not None   # iter2 冻结（user_b 签入）
        assert iters[2].check_in_date is None       # iter3 草稿
        assert iters[2].author_id == _USER_B_ID     # iter3 由 user_b 签入时生成，作者是 user_b
