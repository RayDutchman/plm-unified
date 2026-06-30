"""
M2 Phase A 测试：PartIteration 更新（components + cadInstances）+ 矩阵合成。

测试策略：
  - crud 层直接调用，SQLite 内存库
  - 矩阵合成用已知输入验算输出（单位矩阵、纯平移、纯旋转、MATRIX 模式）
"""
import math
import uuid

import numpy as np
import pytest
from fastapi import HTTPException

from app.crud.assembly import (
    _cad_instance_to_matrix,
    compute_instances,
    write_components,
)
from app.crud.part import checkin, create_part
from app.models import User, Workspace
from app.models.assembly import CADInstance, PartUsageLink
from app.models.part import PartIteration, PartMaster, PartRevision
from app.schemas.assembly import CADInstanceCreate, UsageLinkCreate
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
        id=uuid.uuid4(),
        workspace_id=workspace.id,
        username="user_a",
        password_hash="x",
        real_name="A",
        role="engineer",
    )
    db.add(u)
    db.commit()
    return u


@pytest.fixture
def part_a(db, workspace, user_a):
    """创建零件 A（装配体根节点用），自动签出给 user_a。"""
    return create_part(
        db,
        PartCreate(number="ASM-001", name="装配体", workspace_id=workspace.id),
        author_id=user_a.id,
    )


@pytest.fixture
def part_b(db, workspace, user_a):
    """创建零件 B（子件）并签入，使其有已冻结的迭代可用。"""
    master = create_part(
        db,
        PartCreate(number="PART-B", name="子件B", workspace_id=workspace.id),
        author_id=user_a.id,
    )
    checkin(db, "PART-B", "A", workspace.id, current_user_id=user_a.id)
    return master


@pytest.fixture
def part_c(db, workspace, user_a):
    """创建零件 C（子件）并签入。"""
    master = create_part(
        db,
        PartCreate(number="PART-C", name="子件C", workspace_id=workspace.id),
        author_id=user_a.id,
    )
    checkin(db, "PART-C", "A", workspace.id, current_user_id=user_a.id)
    return master


# ---------------------------------------------------------------------------
# 2.1 write_components 测试
# ---------------------------------------------------------------------------

class TestWriteComponents:
    def test_write_angle_instance(self, db, workspace, user_a, part_a, part_b):
        """写入一个 ANGLE 模式的 CAD 实例。"""
        write_components(
            db=db,
            number="ASM-001",
            version="A",
            iteration_number=1,
            workspace_id=workspace.id,
            current_user_id=user_a.id,
            components=[
                UsageLinkCreate(
                    component_number="PART-B",
                    amount=1.0,
                    cad_instances=[
                        CADInstanceCreate(
                            rotation_type="ANGLE",
                            tx=10.0, ty=20.0, tz=30.0,
                            rx=0.0, ry=0.0, rz=0.0,
                        )
                    ],
                )
            ],
        )

        links = db.query(PartUsageLink).all()
        assert len(links) == 1
        assert links[0].amount == 1.0

        insts = db.query(CADInstance).all()
        assert len(insts) == 1
        assert insts[0].tx == 10.0
        assert insts[0].rotation_type == "ANGLE"
        assert insts[0].rx == 0.0

    def test_matrix_roundtrip_real_rotation(self, db, workspace, user_a, part_a, part_b):
        """
        写入非单位旋转矩阵（120° 绕 Z 轴），读出后通过 _cad_instance_to_matrix 转换，
        验证结果与期望一致。这是 2.4 发现的核心 bug（列优先存储）的回归测试。
        """
        import math
        cos120 = math.cos(2 * math.pi / 3)  # -0.5
        sin120 = math.sin(2 * math.pi / 3)  # 0.866...

        # 绕 Z 轴 120° 旋转矩阵（行优先输入）：
        # R = [[cos, -sin, 0],
        #      [sin,  cos, 0],
        #      [0,    0,   1]]
        matrix_row_major = [
            cos120, -sin120, 0.0,
            sin120,  cos120, 0.0,
            0.0,     0.0,    1.0,
        ]

        write_components(
            db=db,
            number="ASM-001", version="A", iteration_number=1,
            workspace_id=workspace.id, current_user_id=user_a.id,
            components=[
                UsageLinkCreate(
                    component_number="PART-B",
                    cad_instances=[
                        CADInstanceCreate(
                            rotation_type="MATRIX",
                            tx=10.0, ty=20.0, tz=0.0,
                            matrix=matrix_row_major,
                        )
                    ],
                )
            ],
        )

        inst = db.query(CADInstance).first()
        assert inst.rotation_type == "MATRIX"

        # 读出并转为 4×4 矩阵
        computed = _cad_instance_to_matrix(inst)

        # 期望值：120° 绕 Z 轴 + 平移 (10, 20, 0)
        expected = np.array([
            [cos120, -sin120, 0, 10.0],
            [sin120,  cos120, 0, 20.0],
            [0,       0,      1,  0.0],
            [0,       0,      0,  1.0],
        ])

        np.testing.assert_allclose(computed, expected, atol=1e-10)

    def test_write_matrix_instance(self, db, workspace, user_a, part_a, part_b):
        """写入一个 MATRIX 模式的 CAD 实例（单位矩阵）。"""
        write_components(
            db=db,
            number="ASM-001",
            version="A",
            iteration_number=1,
            workspace_id=workspace.id,
            current_user_id=user_a.id,
            components=[
                UsageLinkCreate(
                    component_number="PART-B",
                    cad_instances=[
                        CADInstanceCreate(
                            rotation_type="MATRIX",
                            tx=5.0, ty=0.0, tz=0.0,
                            matrix=[1, 0, 0, 0, 1, 0, 0, 0, 1],
                        )
                    ],
                )
            ],
        )

        inst = db.query(CADInstance).first()
        assert inst.rotation_type == "MATRIX"
        assert inst.tx == 5.0
        # 单位矩阵以列优先存储：m00=1, m10=0, m20=0, m01=0, m11=1, ...
        assert inst.m00 == 1.0
        assert inst.m11 == 1.0
        assert inst.m22 == 1.0
        assert inst.m01 == 0.0

    def test_overwrite_replaces_all_old_links(self, db, workspace, user_a, part_a, part_b, part_c):
        """第二次写入应完全替换旧的 usage_links。"""
        # 第一次：只有 PART-B
        write_components(
            db=db,
            number="ASM-001", version="A", iteration_number=1,
            workspace_id=workspace.id, current_user_id=user_a.id,
            components=[UsageLinkCreate(component_number="PART-B", cad_instances=[])],
        )
        assert db.query(PartUsageLink).count() == 1

        # 第二次：换成 PART-C（PART-B 应被删除）
        write_components(
            db=db,
            number="ASM-001", version="A", iteration_number=1,
            workspace_id=workspace.id, current_user_id=user_a.id,
            components=[UsageLinkCreate(component_number="PART-C", cad_instances=[])],
        )
        links = db.query(PartUsageLink).all()
        assert len(links) == 1
        assert links[0].component_master_id == part_c.id

    def test_multiple_instances_same_child(self, db, workspace, user_a, part_a, part_b):
        """同一子件可有多个 CAD 实例（阵列）。"""
        write_components(
            db=db,
            number="ASM-001", version="A", iteration_number=1,
            workspace_id=workspace.id, current_user_id=user_a.id,
            components=[
                UsageLinkCreate(
                    component_number="PART-B",
                    amount=4,
                    cad_instances=[
                        CADInstanceCreate(rotation_type="ANGLE", tx=0.0, order=0),
                        CADInstanceCreate(rotation_type="ANGLE", tx=10.0, order=1),
                        CADInstanceCreate(rotation_type="ANGLE", tx=20.0, order=2),
                        CADInstanceCreate(rotation_type="ANGLE", tx=30.0, order=3),
                    ],
                )
            ],
        )
        assert db.query(PartUsageLink).count() == 1
        assert db.query(CADInstance).count() == 4

    def test_frozen_iteration_raises_409(self, db, workspace, user_a, part_a):
        """已签入（冻结）的迭代不可修改。"""
        checkin(db, "ASM-001", "A", workspace.id, current_user_id=user_a.id)
        # iter 1 已冻结，尝试写入应 409
        with pytest.raises(HTTPException) as exc:
            write_components(
                db=db,
                number="ASM-001", version="A", iteration_number=1,
                workspace_id=workspace.id, current_user_id=user_a.id,
                components=[],
            )
        assert exc.value.status_code == 409

    def test_nonexistent_child_raises_404(self, db, workspace, user_a, part_a):
        """子件不存在应抛 404。"""
        with pytest.raises(HTTPException) as exc:
            write_components(
                db=db,
                number="ASM-001", version="A", iteration_number=1,
                workspace_id=workspace.id, current_user_id=user_a.id,
                components=[UsageLinkCreate(component_number="NONEXISTENT", cad_instances=[])],
            )
        assert exc.value.status_code == 404


# ---------------------------------------------------------------------------
# 2.3 矩阵合成测试（_cad_instance_to_matrix）
# ---------------------------------------------------------------------------

class TestCadInstanceToMatrix:
    def _make_inst(self, **kwargs):
        """创建 CADInstance 哨兵对象用于测试（不写 DB）。"""
        class FakeInst:
            rotation_type = "ANGLE"
            tx = ty = tz = 0.0
            rx = ry = rz = 0.0
            m00 = m01 = m02 = m10 = m11 = m12 = m20 = m21 = m22 = None
        inst = FakeInst()
        for k, v in kwargs.items():
            setattr(inst, k, v)
        return inst

    def test_identity_angle(self):
        """零旋转零平移 → 单位矩阵。"""
        inst = self._make_inst()
        mat = _cad_instance_to_matrix(inst)
        np.testing.assert_allclose(mat, np.eye(4), atol=1e-10)

    def test_pure_translation(self):
        """纯平移 (10, 20, 30)。"""
        inst = self._make_inst(tx=10.0, ty=20.0, tz=30.0)
        mat = _cad_instance_to_matrix(inst)
        assert mat[0, 3] == pytest.approx(10.0)
        assert mat[1, 3] == pytest.approx(20.0)
        assert mat[2, 3] == pytest.approx(30.0)
        # 旋转部分仍是单位矩阵
        np.testing.assert_allclose(mat[:3, :3], np.eye(3), atol=1e-10)

    def test_rotation_z_90deg(self):
        """绕 Z 轴旋转 90°：X 轴变 Y 轴。"""
        inst = self._make_inst(rz=math.pi / 2)
        mat = _cad_instance_to_matrix(inst)
        # (1, 0, 0) → (0, 1, 0) after 90° rotation around Z
        result = mat[:3, :3] @ np.array([1, 0, 0])
        np.testing.assert_allclose(result, [0, 1, 0], atol=1e-10)

    def test_matrix_mode_identity(self):
        """MATRIX 模式，单位旋转矩阵 + 平移 (5, 0, 0)。"""
        inst = self._make_inst(
            rotation_type="MATRIX",
            tx=5.0,
            m00=1.0, m10=0.0, m20=0.0,
            m01=0.0, m11=1.0, m21=0.0,
            m02=0.0, m12=0.0, m22=1.0,
        )
        mat = _cad_instance_to_matrix(inst)
        assert mat[0, 3] == pytest.approx(5.0)
        np.testing.assert_allclose(mat[:3, :3], np.eye(3), atol=1e-10)

    def test_matrix_composition(self):
        """矩阵累乘：parent (translate +1 on X) × child (translate +1 on Y) = translate (+1,+1,0)。"""
        parent = np.eye(4)
        parent[0, 3] = 1.0

        class InstY:
            rotation_type = "ANGLE"
            tx = 0.0; ty = 1.0; tz = 0.0
            rx = ry = rz = 0.0
            m00 = m01 = m02 = m10 = m11 = m12 = m20 = m21 = m22 = None

        child_mat = _cad_instance_to_matrix(InstY())
        combined = parent @ child_mat
        assert combined[0, 3] == pytest.approx(1.0)
        assert combined[1, 3] == pytest.approx(1.0)
        assert combined[2, 3] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# 2.3 compute_instances 端到端测试
# ---------------------------------------------------------------------------

class TestComputeInstances:
    def test_leaf_node_returns_identity(self, db, workspace, user_a, part_b):
        """单独叶子零件（无子件）返回单位矩阵。"""
        results = compute_instances(
            db=db,
            root_number="PART-B",
            root_version="A",
            workspace_id=workspace.id,
        )
        assert len(results) == 1
        mat = np.array(results[0].matrix).reshape(4, 4)
        np.testing.assert_allclose(mat, np.eye(4), atol=1e-10)

    def test_one_level_assembly_translation(
        self, db, workspace, user_a, part_a, part_b
    ):
        """
        简单一层装配：ASM-001 包含 PART-B，PART-B 在 (+10, +20, +30)。
        预期 PART-B 的全局矩阵平移部分 = (10, 20, 30)。
        """
        # 写入 components
        write_components(
            db=db,
            number="ASM-001", version="A", iteration_number=1,
            workspace_id=workspace.id, current_user_id=user_a.id,
            components=[
                UsageLinkCreate(
                    component_number="PART-B",
                    cad_instances=[
                        CADInstanceCreate(
                            rotation_type="ANGLE",
                            tx=10.0, ty=20.0, tz=30.0,
                        )
                    ],
                )
            ],
        )
        # 签入 ASM-001（使其成为可查询的已签入迭代）
        checkin(db, "ASM-001", "A", workspace.id, current_user_id=user_a.id)

        results = compute_instances(
            db=db,
            root_number="ASM-001",
            root_version="A",
            workspace_id=workspace.id,
        )
        assert len(results) == 1
        assert results[0].part_number == "PART-B"
        mat = np.array(results[0].matrix).reshape(4, 4)
        assert mat[0, 3] == pytest.approx(10.0)
        assert mat[1, 3] == pytest.approx(20.0)
        assert mat[2, 3] == pytest.approx(30.0)

    def test_two_children_returns_two_results(
        self, db, workspace, user_a, part_a, part_b, part_c
    ):
        """装配体有两个子件，返回 2 条结果。"""
        write_components(
            db=db,
            number="ASM-001", version="A", iteration_number=1,
            workspace_id=workspace.id, current_user_id=user_a.id,
            components=[
                UsageLinkCreate(
                    component_number="PART-B",
                    cad_instances=[CADInstanceCreate(rotation_type="ANGLE", tx=0.0)],
                ),
                UsageLinkCreate(
                    component_number="PART-C",
                    cad_instances=[CADInstanceCreate(rotation_type="ANGLE", tx=50.0)],
                ),
            ],
        )
        checkin(db, "ASM-001", "A", workspace.id, current_user_id=user_a.id)

        results = compute_instances(
            db=db,
            root_number="ASM-001",
            root_version="A",
            workspace_id=workspace.id,
        )
        assert len(results) == 2
        numbers = {r.part_number for r in results}
        assert numbers == {"PART-B", "PART-C"}

    def test_same_child_multiple_instances(
        self, db, workspace, user_a, part_a, part_b
    ):
        """同一子件 3 个实例 → 返回 3 条结果，平移各不同。"""
        write_components(
            db=db,
            number="ASM-001", version="A", iteration_number=1,
            workspace_id=workspace.id, current_user_id=user_a.id,
            components=[
                UsageLinkCreate(
                    component_number="PART-B",
                    amount=3,
                    cad_instances=[
                        CADInstanceCreate(rotation_type="ANGLE", tx=0.0, order=0),
                        CADInstanceCreate(rotation_type="ANGLE", tx=100.0, order=1),
                        CADInstanceCreate(rotation_type="ANGLE", tx=200.0, order=2),
                    ],
                )
            ],
        )
        checkin(db, "ASM-001", "A", workspace.id, current_user_id=user_a.id)

        results = compute_instances(
            db=db,
            root_number="ASM-001",
            root_version="A",
            workspace_id=workspace.id,
        )
        assert len(results) == 3
        tx_values = sorted(r.matrix[3] for r in results)  # index 3 = row0, col3 = tx
        assert tx_values == pytest.approx([0.0, 100.0, 200.0])
