"""
M2 Phase B 测试：转换回调（2.7）和状态查询（2.8）。

2.5 的文件上传涉及真实文件系统和 Kafka，在集成测试中覆盖；
这里测试不依赖 I/O 的 crud 层逻辑。
"""
import uuid
from datetime import datetime

import pytest

from app.crud.conversion import (
    get_conversion_status,
    handle_conversion_callback,
)
from app.crud.part import checkin, create_part
from app.models import User, Workspace
from app.models.binary import BinaryResource, Conversion, Geometry
from app.models.part import PartIteration
from app.schemas.part import PartCreate


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def workspace(db):
    ws = Workspace(id=uuid.uuid4(), name="test-ws")
    db.add(ws)
    db.commit()
    return ws


@pytest.fixture
def user_a(db, workspace):
    u = User(
        id=uuid.uuid4(), workspace_id=workspace.id,
        username="user_a", password_hash="x",
        real_name="A", role="engineer",
    )
    db.add(u)
    db.commit()
    return u


@pytest.fixture
def part_and_iteration(db, workspace, user_a):
    """创建零件并在迭代上绑定一个 BinaryResource（模拟已上传 CAD 文件）。"""
    master = create_part(
        db, PartCreate(number="CONV-001", name="转换测试件", workspace_id=workspace.id),
        author_id=user_a.id,
    )
    # 取 iteration 1
    from app.models.part import PartRevision
    revision = db.query(PartRevision).filter_by(part_master_id=master.id).first()
    iteration = db.query(PartIteration).filter_by(part_revision_id=revision.id).first()

    # 绑定 native_cad_file（模拟 2.5 已上传）
    br = BinaryResource(
        id=uuid.uuid4(),
        full_name="test-ws/parts/CONV-001/A/1/nativecad/model.stp",
        content_length=1024,
    )
    db.add(br)
    iteration.native_cad_file_id = br.id
    db.flush()

    # 创建 Conversion pending 记录（模拟 2.5 触发转换后）
    conv = Conversion(
        id=uuid.uuid4(),
        iteration_id=iteration.id,
        pending=True,
        succeed=None,
    )
    db.add(conv)
    db.commit()

    return master, iteration, br


# ---------------------------------------------------------------------------
# 2.7 handle_conversion_callback 测试
# ---------------------------------------------------------------------------

class TestConversionCallback:
    def test_callback_success_writes_geometry(self, db, workspace, user_a, part_and_iteration):
        """成功回调：写入 Geometry + 更新 Conversion 状态。"""
        master, iteration, br = part_and_iteration

        handle_conversion_callback(
            db=db,
            number="CONV-001", version="A", iteration_number=1,
            workspace_id=workspace.id,
            succeed=True,
            geometry_full_name="test-ws/parts/CONV-001/A/1/geometries/model.glb",
            x_min=-10.0, y_min=-10.0, z_min=-10.0,
            x_max=10.0,  y_max=10.0,  z_max=10.0,
            quality=0,
            content_length=5120,
        )

        # Conversion 状态更新
        conv = db.query(Conversion).filter_by(iteration_id=iteration.id).first()
        assert conv.pending is False
        assert conv.succeed is True
        assert conv.end_date is not None

        # Geometry 已写入
        geo = db.query(Geometry).filter_by(iteration_id=iteration.id).first()
        assert geo is not None
        assert geo.quality == 0
        assert geo.x_min == pytest.approx(-10.0)
        assert geo.x_max == pytest.approx(10.0)

        # BinaryResource（geometry 文件）已创建
        geo_br = db.get(BinaryResource, geo.binary_resource_id)
        assert geo_br.full_name == "test-ws/parts/CONV-001/A/1/geometries/model.glb"

    def test_callback_failure_updates_status_only(self, db, workspace, user_a, part_and_iteration):
        """失败回调：只更新状态，不写 Geometry。"""
        master, iteration, _ = part_and_iteration

        handle_conversion_callback(
            db=db,
            number="CONV-001", version="A", iteration_number=1,
            workspace_id=workspace.id,
            succeed=False,
        )

        conv = db.query(Conversion).filter_by(iteration_id=iteration.id).first()
        assert conv.pending is False
        assert conv.succeed is False

        geo_count = db.query(Geometry).filter_by(iteration_id=iteration.id).count()
        assert geo_count == 0

    def test_callback_replaces_old_geometry_same_quality(self, db, workspace, user_a, part_and_iteration):
        """重复回调同一 quality=0 的 geometry 时，旧记录被替换。"""
        master, iteration, _ = part_and_iteration

        # 第一次成功
        handle_conversion_callback(
            db=db,
            number="CONV-001", version="A", iteration_number=1,
            workspace_id=workspace.id,
            succeed=True,
            geometry_full_name="test-ws/parts/CONV-001/A/1/geometries/model_v1.glb",
            x_min=-5.0, y_min=-5.0, z_min=-5.0,
            x_max=5.0, y_max=5.0, z_max=5.0,
        )
        assert db.query(Geometry).filter_by(iteration_id=iteration.id).count() == 1

        # 创建新 Conversion pending 记录（模拟重试上传）
        db.add(Conversion(
            id=uuid.uuid4(), iteration_id=iteration.id,
            pending=True, succeed=None,
        ))
        db.commit()

        # 第二次成功（新文件）
        handle_conversion_callback(
            db=db,
            number="CONV-001", version="A", iteration_number=1,
            workspace_id=workspace.id,
            succeed=True,
            geometry_full_name="test-ws/parts/CONV-001/A/1/geometries/model_v2.glb",
            x_min=-8.0, y_min=-8.0, z_min=-8.0,
            x_max=8.0, y_max=8.0, z_max=8.0,
        )
        # 只有一条 quality=0 的 geometry
        geos = db.query(Geometry).filter_by(iteration_id=iteration.id).all()
        assert len(geos) == 1
        geo_br = db.get(BinaryResource, geos[0].binary_resource_id)
        assert "v2" in geo_br.full_name


# ---------------------------------------------------------------------------
# 2.8 get_conversion_status 测试
# ---------------------------------------------------------------------------

class TestConversionStatus:
    def test_no_conversion_record(self, db, workspace, user_a):
        """没有转换记录时返回 pending=false, succeed=null。"""
        create_part(
            db, PartCreate(number="NO-CONV", name="无转换记录", workspace_id=workspace.id),
            author_id=user_a.id,
        )
        result = get_conversion_status(
            db=db, number="NO-CONV", version="A", iteration_number=1,
            workspace_id=workspace.id,
        )
        assert result["pending"] is False
        assert result["succeed"] is None

    def test_pending_status(self, db, workspace, user_a, part_and_iteration):
        """转换中状态：pending=true。"""
        result = get_conversion_status(
            db=db, number="CONV-001", version="A", iteration_number=1,
            workspace_id=workspace.id,
        )
        assert result["pending"] is True
        assert result["succeed"] is None

    def test_success_status(self, db, workspace, user_a, part_and_iteration):
        """成功后：pending=false, succeed=true。"""
        handle_conversion_callback(
            db=db, number="CONV-001", version="A", iteration_number=1,
            workspace_id=workspace.id, succeed=True,
            geometry_full_name="test-ws/parts/CONV-001/A/1/geometries/model.glb",
            x_min=0, y_min=0, z_min=0, x_max=1, y_max=1, z_max=1,
        )
        result = get_conversion_status(
            db=db, number="CONV-001", version="A", iteration_number=1,
            workspace_id=workspace.id,
        )
        assert result["pending"] is False
        assert result["succeed"] is True
        assert result["startDate"] is not None
        assert result["endDate"] is not None
