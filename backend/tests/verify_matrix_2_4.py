"""
2.4 矩阵合成验证脚本

用旧 DocDoku 数据库中的真实装配体数据（Assem1, Workspace_2, iteration 12）
验证 Python 实现的矩阵合成结果与原始 Java 端存储的矩阵一致。

由于 Assem1 是一层平铺装配（所有子件都是叶子），
父矩阵 = 单位矩阵，所以全局矩阵 = CADInstance 自身的变换矩阵。
这等价于直接验证 _cad_instance_to_matrix() 对 MATRIX 模式的正确性。

验证方式：
  Python 计算：matrix = _cad_instance_to_matrix(inst)
  预期值：从数据库读出的 m00~m22 + tx/ty/tz 直接构成的 4×4 矩阵
  误差要求：逐元素 < 1e-10（考虑浮点噪声）
"""
import sys
import os

# 将 backend/ 加入路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import numpy as np

# 直接导入矩阵转换函数（不需要 DB）
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET", "test-secret-key-for-tests-only-xx")

from app.crud.assembly import _cad_instance_to_matrix


# ---------------------------------------------------------------------------
# 测试数据：从旧 DocDoku DB 查出的 Assem1 iteration 12 全部 CADInstance
# 每条记录格式：(cad_instance_id, component, tx,ty,tz, rotationtype, m00..m22)
# ---------------------------------------------------------------------------

# 取其中有代表性的 5 条：包含几乎零矩阵（近似单位旋转）和有明确旋转的矩阵
DOCDOKU_INSTANCES = [
    # (component, tx, ty, tz, m_row_major_9)
    # m_row_major_9 = [m00,m01,m02, m10,m11,m12, m20,m21,m22]
    # 注意：DocDoku 存列优先（m{col}{row}），读出来时字段名 m{col}{row}
    # 所以字段 m00=列0行0, m10=列1行0, m20=列2行0
    #         m01=列0行1, m11=列1行1, m21=列2行1
    #         m02=列0行2, m12=列1行2, m22=列2行2
    # 即实际矩阵 R[row][col] = m{col}{row}

    # Differential Axle 2010, instance 0: 近似单位矩阵，tz=0
    {
        "id": 5403,
        "component": "Differential Axle 2010",
        "tx": 0, "ty": 0, "tz": 0,
        "m00": 1, "m01": 0, "m02": 0,
        "m10": 0, "m11": 1, "m12": 0,
        "m20": 0, "m21": 0, "m22": 1,
    },
    # Limited-Slip Differential Cover, tz=27.35, 近似单位矩阵
    {
        "id": 5381,
        "component": "Limited-Slip Differential Cover",
        "tx": 1.08506123061476e-14, "ty": 2.28966250973321e-15, "tz": 27.35,
        "m00": 1, "m01": 0, "m02": 0,
        "m10": 0, "m11": 1, "m12": 0,
        "m20": 0, "m21": 0, "m22": 1,
    },
    # Limited-Slip Differential Housing, 有旋转
    {
        "id": 5413,
        "component": "Limited-Slip Differential Housing",
        "tx": 0, "ty": 0, "tz": 0,
        "m00": -1.66533453693773e-16, "m01": 1,                 "m02": 8.326672684688674e-17,
        "m10": 1,                     "m11": 1.6653345369377301e-16, "m12": -2.0573140676162199e-16,
        "m20": -2.05731406761622e-16, "m21": 8.32667268468867e-17,  "m22": -1,
    },
    # Copper Washer instance 1: 120° 旋转 + 平移
    {
        "id": 5407,
        "component": "Copper Washer (120deg rotated)",
        "tx": -22.125, "ty": 38.3216241174614, "tz": 8.10000011307295e-15,
        "m00": 0.8660254037844388,  "m01": 0.4999999999999999,   "m02": 1.2358774653135196e-16,
        "m10": -1.4117122827514467e-16, "m11": -2.659753123249219e-18, "m12": 1,
        "m20": 0.4999999999999999,  "m21": -0.8660254037844388,  "m22": 6.828220036504349e-17,
    },
    # Copper Washer instance 2: 另一个 120° 旋转
    {
        "id": 5390,
        "component": "Copper Washer (240deg rotated)",
        "tx": -22.125, "ty": -38.3216241174614, "tz": -4.67056049142314e-15,
        "m00": -3.6955965795549236e-18, "m01": -2.3724373088692214e-16, "m02": 1,
        "m10": 0.8660254037844388,     "m11": -0.4999999999999999,     "m12": -1.154213849234276e-16,
        "m20": 0.4999999999999999,     "m21": 0.8660254037844388,      "m22": 2.0730689612645095e-16,
    },
]


def db_mat_to_4x4(inst: dict) -> np.ndarray:
    """
    把从 DocDoku DB 读出的 m{col}{row} 字段还原为 4×4 行优先矩阵。

    DocDoku RotationMatrix 字段命名：m{col}{row}（列优先存储）
    即：
      第 0 列：m00=R[0][0], m10=R[1][0], m20=R[2][0]
      第 1 列：m01=R[0][1], m11=R[1][1], m21=R[2][1]
      第 2 列：m02=R[0][2], m12=R[1][2], m22=R[2][2]
    """
    mat = np.eye(4, dtype=float)
    # 列 0 → 矩阵第 0 列
    mat[0, 0] = inst["m00"]; mat[1, 0] = inst["m10"]; mat[2, 0] = inst["m20"]
    # 列 1 → 矩阵第 1 列
    mat[0, 1] = inst["m01"]; mat[1, 1] = inst["m11"]; mat[2, 1] = inst["m21"]
    # 列 2 → 矩阵第 2 列
    mat[0, 2] = inst["m02"]; mat[1, 2] = inst["m12"]; mat[2, 2] = inst["m22"]
    # 平移列
    mat[0, 3] = inst["tx"]; mat[1, 3] = inst["ty"]; mat[2, 3] = inst["tz"]
    return mat


class FakeCADInstance:
    """模拟 SQLAlchemy ORM 对象，用于传给 _cad_instance_to_matrix()。"""
    def __init__(self, d: dict):
        self.rotation_type = "MATRIX"
        self.tx = d["tx"]; self.ty = d["ty"]; self.tz = d["tz"]
        # 注意：ORM 存的是与 DB 一致的列优先字段
        # _cad_instance_to_matrix 的 MATRIX 分支直接读 m{col}{row}
        self.m00 = d["m00"]; self.m01 = d["m01"]; self.m02 = d["m02"]
        self.m10 = d["m10"]; self.m11 = d["m11"]; self.m12 = d["m12"]
        self.m20 = d["m20"]; self.m21 = d["m21"]; self.m22 = d["m22"]
        self.rx = self.ry = self.rz = None


def verify():
    print("=" * 70)
    print("2.4 矩阵合成验证：Python vs DocDoku DB (Assem1, Workspace_2, iter 12)")
    print("=" * 70)
    print()

    all_pass = True
    max_err = 0.0

    for inst_data in DOCDOKU_INSTANCES:
        component = inst_data["component"]
        inst_id = inst_data["id"]

        # DocDoku DB 期望值：直接从字段还原
        expected = db_mat_to_4x4(inst_data)

        # Python 计算值
        fake_inst = FakeCADInstance(inst_data)
        computed = _cad_instance_to_matrix(fake_inst)

        # 误差
        diff = np.abs(computed - expected)
        max_diff = diff.max()
        max_err = max(max_err, max_diff)

        passed = max_diff < 1e-10
        status = "✅ PASS" if passed else "❌ FAIL"
        if not passed:
            all_pass = False

        print(f"{status}  [{inst_id:4d}] {component[:45]:<45}")
        print(f"         max_diff = {max_diff:.2e}")

        if not passed:
            print(f"  Expected:\n{expected}")
            print(f"  Computed:\n{computed}")
            print(f"  Diff:\n{diff}")
        print()

    print("-" * 70)
    print(f"全局最大误差: {max_err:.2e}")
    if all_pass:
        print("✅ 所有验证通过 — Python 矩阵合成与 DocDoku 数据库结果完全一致（误差 < 1e-10）")
    else:
        print("❌ 部分验证失败，需要检查矩阵存储/读取逻辑")
    print()
    return all_pass


if __name__ == "__main__":
    ok = verify()
    sys.exit(0 if ok else 1)
