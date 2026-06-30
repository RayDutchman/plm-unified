"""
M1.6/M1.7 零件 CRUD + 签入签出状态机测试。

测试策略：
  - 使用 conftest.py 提供的 SQLite 内存库 fixture（已含 FK 强制）
  - 直接调 crud 层函数，不走 HTTP，覆盖业务规则最干净
  - 状态机三个 409 场景是 M1 验收核心
"""
import uuid
from datetime import timezone

import pytest
from fastapi import HTTPException

from app.crud.part import (
    checkin,
    checkout,
    create_part,
    get_part,
    list_parts,
    undocheckout,
)
from app.models.part import PartIteration, PartRevision
from app.models.user import User
from app.models.workspace import Workspace
from app.schemas.part import PartCreate


# ---------------------------------------------------------------------------
# Fixtures：种子数据
# ---------------------------------------------------------------------------

@pytest.fixture
def workspace(db):
    ws = Workspace(
        id=uuid.uuid4(),
        name="test-workspace",
    )
    db.add(ws)
    db.commit()
    return ws


@pytest.fixture
def user_a(db, workspace):
    u = User(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        username="user_a",
        password_hash="hashed",
        real_name="用户 A",
        role="engineer",
    )
    db.add(u)
    db.commit()
    return u


@pytest.fixture
def user_b(db, workspace):
    u = User(
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        username="user_b",
        password_hash="hashed",
        real_name="用户 B",
        role="engineer",
    )
    db.add(u)
    db.commit()
    return u


@pytest.fixture
def sample_part_data(workspace):
    return PartCreate(
        number="PART-001",
        name="测试零件",
        workspace_id=workspace.id,
    )


# ---------------------------------------------------------------------------
# 1.6 CRUD 测试
# ---------------------------------------------------------------------------

class TestCreatePart:
    def test_creates_three_layers(self, db, sample_part_data, user_a):
        """创建零件应自动生成 PartRevision(A,WIP) + PartIteration(1)。"""
        master = create_part(db, sample_part_data, author_id=user_a.id)

        assert master.number == "PART-001"
        assert master.workspace_id == sample_part_data.workspace_id

        rev = db.query(PartRevision).filter_by(part_master_id=master.id).first()
        assert rev is not None
        assert rev.version == "A"
        assert rev.status == "WIP"
        # 创建后自动签出给作者
        assert rev.checkout_user_id == user_a.id

        itr = db.query(PartIteration).filter_by(part_revision_id=rev.id).first()
        assert itr is not None
        assert itr.iteration == 1
        assert itr.check_in_date is None  # 未签入

    def test_duplicate_number_raises_409(self, db, sample_part_data, user_a):
        """同工作空间重复编号应抛 409。"""
        create_part(db, sample_part_data, author_id=user_a.id)
        with pytest.raises(HTTPException) as exc_info:
            create_part(db, sample_part_data, author_id=user_a.id)
        assert exc_info.value.status_code == 409

    def test_different_workspace_same_number_ok(self, db, workspace, user_a):
        """不同工作空间允许相同编号。"""
        ws2 = Workspace(id=uuid.uuid4(), name="ws2")
        db.add(ws2)
        db.commit()

        data1 = PartCreate(number="SHARED-001", name="零件1", workspace_id=workspace.id)
        data2 = PartCreate(number="SHARED-001", name="零件2", workspace_id=ws2.id)
        # user_a 属于 workspace，但 workspace_id 不同，FK 指向不同 ws —— 此处 user_a 归属 workspace，
        # 创建 ws2 的零件时 author_id 仍可用（author_id FK 指向 users，不受 workspace 限制）
        m1 = create_part(db, data1, author_id=user_a.id)
        m2 = create_part(db, data2, author_id=user_a.id)
        assert m1.id != m2.id


class TestGetAndListParts:
    def test_get_part_returns_correct(self, db, sample_part_data, user_a):
        master = create_part(db, sample_part_data, author_id=user_a.id)
        found = get_part(db, number="PART-001", workspace_id=sample_part_data.workspace_id)
        assert found.id == master.id

    def test_get_nonexistent_raises_404(self, db, workspace):
        with pytest.raises(HTTPException) as exc_info:
            get_part(db, number="NONEXISTENT", workspace_id=workspace.id)
        assert exc_info.value.status_code == 404

    def test_list_parts_paging(self, db, workspace, user_a):
        for i in range(5):
            create_part(
                db,
                PartCreate(number=f"P-{i:03d}", name=f"零件{i}", workspace_id=workspace.id),
                author_id=user_a.id,
            )
        page1 = list_parts(db, workspace_id=workspace.id, skip=0, limit=3)
        page2 = list_parts(db, workspace_id=workspace.id, skip=3, limit=3)
        assert len(page1) == 3
        assert len(page2) == 2

    def test_list_excludes_soft_deleted(self, db, workspace, user_a):
        from app.models.part import PartMaster
        from datetime import datetime
        master = create_part(
            db,
            PartCreate(number="DEL-001", name="待删零件", workspace_id=workspace.id),
            author_id=user_a.id,
        )
        master.deleted_at = datetime.now(timezone.utc)
        db.commit()
        parts = list_parts(db, workspace_id=workspace.id)
        assert all(p.id != master.id for p in parts)


# ---------------------------------------------------------------------------
# 1.7 签入签出状态机测试
# ---------------------------------------------------------------------------

class TestCheckout:
    def test_checkout_sets_lock(self, db, sample_part_data, user_a, user_b):
        """签出后 checkout_user_id 应被设置。"""
        master = create_part(db, sample_part_data, author_id=user_a.id)
        # 创建时已被 user_a 签出，先签入清锁
        checkin(db, "PART-001", "A", master.workspace_id, current_user_id=user_a.id)

        rev = checkout(db, "PART-001", "A", master.workspace_id, current_user_id=user_b.id)
        assert rev.checkout_user_id == user_b.id
        assert rev.checkout_date is not None

    def test_checkout_already_checkedout_raises_409(self, db, sample_part_data, user_a, user_b):
        """已签出的版本被另一用户签出应抛 409。"""
        create_part(db, sample_part_data, author_id=user_a.id)
        # user_a 已签出，user_b 尝试签出应 409
        with pytest.raises(HTTPException) as exc_info:
            checkout(db, "PART-001", "A", sample_part_data.workspace_id, current_user_id=user_b.id)
        assert exc_info.value.status_code == 409

    def test_checkout_released_version_raises_409(self, db, sample_part_data, user_a):
        """已发布版本不可签出，应抛 409。"""
        create_part(db, sample_part_data, author_id=user_a.id)
        # 直接把 revision.status 改为 RELEASED 模拟已发布
        rev = db.query(PartRevision).filter_by(version="A").first()
        rev.status = "RELEASED"
        rev.checkout_user_id = None
        db.commit()

        with pytest.raises(HTTPException) as exc_info:
            checkout(db, "PART-001", "A", sample_part_data.workspace_id, current_user_id=user_a.id)
        assert exc_info.value.status_code == 409


class TestCheckin:
    def test_checkin_freezes_iteration_and_creates_next(self, db, sample_part_data, user_a):
        """签入应冻结当前迭代并创建下一迭代。"""
        master = create_part(db, sample_part_data, author_id=user_a.id)
        rev = checkin(db, "PART-001", "A", master.workspace_id, current_user_id=user_a.id)

        assert rev.checkout_user_id is None
        assert rev.checkout_date is None

        iters = (
            db.query(PartIteration)
            .filter_by(part_revision_id=rev.id)
            .order_by(PartIteration.iteration)
            .all()
        )
        assert len(iters) == 2
        assert iters[0].iteration == 1
        assert iters[0].check_in_date is not None  # 已冻结
        assert iters[1].iteration == 2
        assert iters[1].check_in_date is None  # 新草稿

    def test_checkin_not_checked_out_raises_409(self, db, sample_part_data, user_a):
        """未签出状态下签入应抛 409。"""
        master = create_part(db, sample_part_data, author_id=user_a.id)
        # 先签入清锁
        checkin(db, "PART-001", "A", master.workspace_id, current_user_id=user_a.id)
        # 现在未签出，再次签入应 409
        with pytest.raises(HTTPException) as exc_info:
            checkin(db, "PART-001", "A", master.workspace_id, current_user_id=user_a.id)
        assert exc_info.value.status_code == 409

    def test_checkin_by_non_owner_raises_409(self, db, sample_part_data, user_a, user_b):
        """非签出本人签入应抛 409。"""
        create_part(db, sample_part_data, author_id=user_a.id)
        # user_a 签出，user_b 尝试签入
        with pytest.raises(HTTPException) as exc_info:
            checkin(db, "PART-001", "A", sample_part_data.workspace_id, current_user_id=user_b.id)
        assert exc_info.value.status_code == 409


class TestUndoCheckout:
    def test_undocheckout_discards_draft_iteration(self, db, sample_part_data, user_a):
        """撤销签出应清签出锁，且若草稿迭代 iteration > 1 应删除。"""
        master = create_part(db, sample_part_data, author_id=user_a.id)
        # 签入生成 iteration 2（草稿），再签出
        checkin(db, "PART-001", "A", master.workspace_id, current_user_id=user_a.id)
        checkout(db, "PART-001", "A", master.workspace_id, current_user_id=user_a.id)

        rev = undocheckout(db, "PART-001", "A", master.workspace_id, current_user_id=user_a.id)
        assert rev.checkout_user_id is None

        # iteration 2（草稿）应被删除，只剩 iteration 1
        iters = (
            db.query(PartIteration)
            .filter_by(part_revision_id=rev.id)
            .order_by(PartIteration.iteration)
            .all()
        )
        assert len(iters) == 1
        assert iters[0].iteration == 1

    def test_undocheckout_on_iteration_1_keeps_iteration(self, db, sample_part_data, user_a):
        """
        iteration==1 时撤销签出：清签出锁但不删除 iteration 1。
        （iteration 1 是零件的首个迭代，即使从未签入也不应被删除，
         因为设计上 iteration > 1 才是"可丢弃的草稿"）
        """
        master = create_part(db, sample_part_data, author_id=user_a.id)
        # 创建后自动在 iteration 1 处签出，直接撤销（不先签入）

        rev = undocheckout(db, "PART-001", "A", master.workspace_id, current_user_id=user_a.id)
        assert rev.checkout_user_id is None

        # iteration 1 应保留（不删除）
        iters = (
            db.query(PartIteration)
            .filter_by(part_revision_id=rev.id)
            .all()
        )
        assert len(iters) == 1
        assert iters[0].iteration == 1
        assert iters[0].check_in_date is None  # 仍是草稿（从未签入）

    def test_undocheckout_not_checked_out_raises_409(self, db, sample_part_data, user_a):
        """未签出时撤销应抛 409。"""
        master = create_part(db, sample_part_data, author_id=user_a.id)
        checkin(db, "PART-001", "A", master.workspace_id, current_user_id=user_a.id)
        # 现在未签出，撤销应 409
        with pytest.raises(HTTPException) as exc_info:
            undocheckout(db, "PART-001", "A", master.workspace_id, current_user_id=user_a.id)
        assert exc_info.value.status_code == 409

    def test_undocheckout_by_non_owner_raises_409(self, db, sample_part_data, user_a, user_b):
        """非签出本人撤销应抛 409。"""
        create_part(db, sample_part_data, author_id=user_a.id)
        with pytest.raises(HTTPException) as exc_info:
            undocheckout(db, "PART-001", "A", sample_part_data.workspace_id, current_user_id=user_b.id)
        assert exc_info.value.status_code == 409


class TestFullFlow:
    def test_full_checkin_checkout_cycle(self, db, workspace, user_a, user_b):
        """
        完整流程验收：
          创建 → 签入 → 第二用户尝试签出（应 409）
          → user_a 签出 → user_b 再签出（409）
          → user_a 签入 → user_b 签出（OK）
        """
        data = PartCreate(number="FLOW-001", name="流程测试件", workspace_id=workspace.id)
        master = create_part(db, data, author_id=user_a.id)

        # 创建后 user_a 自动签出，user_b 尝试签出 → 409
        with pytest.raises(HTTPException) as exc:
            checkout(db, "FLOW-001", "A", workspace.id, current_user_id=user_b.id)
        assert exc.value.status_code == 409

        # user_a 签入，生成 iteration 2
        rev = checkin(db, "FLOW-001", "A", workspace.id, current_user_id=user_a.id)
        assert rev.checkout_user_id is None

        # user_b 现在可以签出
        rev = checkout(db, "FLOW-001", "A", workspace.id, current_user_id=user_b.id)
        assert rev.checkout_user_id == user_b.id

        # user_a 尝试签出（已被 user_b 持锁） → 409
        with pytest.raises(HTTPException) as exc:
            checkout(db, "FLOW-001", "A", workspace.id, current_user_id=user_a.id)
        assert exc.value.status_code == 409

        # user_b 签入
        rev = checkin(db, "FLOW-001", "A", workspace.id, current_user_id=user_b.id)
        assert rev.checkout_user_id is None

        # 验证迭代历史：1（冻结）、2（冻结）、3（草稿）
        iters = (
            db.query(PartIteration)
            .filter_by(part_revision_id=rev.id)
            .order_by(PartIteration.iteration)
            .all()
        )
        assert len(iters) == 3
        assert iters[0].check_in_date is not None
        assert iters[1].check_in_date is not None
        assert iters[2].check_in_date is None
