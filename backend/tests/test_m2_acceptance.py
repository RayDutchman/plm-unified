"""
M2 验收测试（2.10）

覆盖 M2 达成条件：
  - 通过 API 写入装配体 BOM（components + cadInstances）
  - 矩阵合成接口返回正确的全局 mat4
  - CAD 文件上传（mock vault）触发转换流程
  - 转换回调写入 Geometry
  - 转换状态轮询返回正确状态

部分依赖 I/O / Kafka 的步骤通过 monkeypatch 测试逻辑正确性。
"""
import math
import os
import uuid
from io import BytesIO
from unittest.mock import AsyncMock, patch

import numpy as np
import pytest
from fastapi.testclient import TestClient

from app.core.security import get_password_hash
from app.database import get_db
from app.main import app
from app.models import User, Workspace
from app.models.part import PartIteration, PartMaster, PartRevision


# ---------------------------------------------------------------------------
# 常量
# ---------------------------------------------------------------------------
_WS_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")
_WS_NAME = "test-workspace"
_ADMIN_ID = uuid.UUID("00000000-0000-0000-0000-000000000010")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def client(db):
    ws = Workspace(id=_WS_ID, name=_WS_NAME)
    db.add(ws)
    db.flush()
    admin = User(
        id=_ADMIN_ID, workspace_id=_WS_ID,
        username="admin", password_hash=get_password_hash("admin12345"),
        real_name="管理员", role="admin", status="active",
    )
    db.add(admin)
    db.commit()

    def _override_get_db():
        yield db

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _login(client: TestClient) -> dict:
    r = client.post("/api/auth/token", data={"username": "admin", "password": "admin12345"})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


# ---------------------------------------------------------------------------
# M2 验收测试
# ---------------------------------------------------------------------------

class TestM2Acceptance:

    def test_01_write_components_and_compute_matrix(self, client):
        """
        创建装配体 ASM-M2 + 子件 LEAF-M2，
        写入 BOM（LEAF-M2 在 tx=50mm），
        矩阵合成接口返回 tx=50 的全局矩阵。
        """
        headers = _login(client)

        # 创建叶子零件并签入
        client.post("/api/parts", json={
            "number": "LEAF-M2", "name": "叶子件",
            "workspaceId": str(_WS_ID),
        }, headers=headers)
        client.put(f"/api/parts/LEAF-M2/A/checkin?workspace_id={_WS_ID}", headers=headers)

        # 创建装配体（自动签出）
        client.post("/api/parts", json={
            "number": "ASM-M2", "name": "装配体",
            "workspaceId": str(_WS_ID),
        }, headers=headers)

        # 写入 BOM：LEAF-M2 在 tx=50mm
        r = client.put(
            f"/api/parts/ASM-M2/A/iterations/1?workspace_id={_WS_ID}",
            json={
                "iterationNote": "装配体验收",
                "components": [
                    {
                        "componentNumber": "LEAF-M2",
                        "amount": 1,
                        "cadInstances": [
                            {
                                "rotationType": "ANGLE",
                                "tx": 50.0, "ty": 0.0, "tz": 0.0,
                                "rx": 0.0, "ry": 0.0, "rz": 0.0,
                            }
                        ],
                    }
                ],
            },
            headers=headers,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert len(body["components"]) == 1
        assert len(body["components"][0]["cadInstances"]) == 1

        # 签入装配体（使其可查询）
        client.put(f"/api/parts/ASM-M2/A/checkin?workspace_id={_WS_ID}", headers=headers)

        # 矩阵合成
        r = client.get(
            f"/api/parts/ASM-M2/A/instances?workspace_id={_WS_ID}",
            headers=headers,
        )
        assert r.status_code == 200, r.text
        instances = r.json()
        assert len(instances) == 1

        inst = instances[0]
        assert inst["partNumber"] == "LEAF-M2"
        mat = np.array(inst["matrix"]).reshape(4, 4)
        # tx=50mm → mat[0,3] = 50
        assert mat[0, 3] == pytest.approx(50.0)
        assert mat[1, 3] == pytest.approx(0.0)
        assert mat[2, 3] == pytest.approx(0.0)
        # 旋转部分应为单位矩阵
        np.testing.assert_allclose(mat[:3, :3], np.eye(3), atol=1e-10)

    def test_02_matrix_mode_components(self, client):
        """
        MATRIX 模式：子件旋转 90°（绕 Z 轴），验证合成矩阵旋转正确。
        """
        headers = _login(client)

        client.post("/api/parts", json={
            "number": "ROT-LEAF", "name": "旋转件", "workspaceId": str(_WS_ID),
        }, headers=headers)
        client.put(f"/api/parts/ROT-LEAF/A/checkin?workspace_id={_WS_ID}", headers=headers)

        client.post("/api/parts", json={
            "number": "ROT-ASM", "name": "旋转装配体", "workspaceId": str(_WS_ID),
        }, headers=headers)

        # 绕 Z 轴 90°：[[0,-1,0],[1,0,0],[0,0,1]]
        cos90 = 0.0; sin90 = 1.0
        client.put(
            f"/api/parts/ROT-ASM/A/iterations/1?workspace_id={_WS_ID}",
            json={
                "components": [{
                    "componentNumber": "ROT-LEAF",
                    "cadInstances": [{
                        "rotationType": "MATRIX",
                        "tx": 0.0, "ty": 0.0, "tz": 0.0,
                        "matrix": [
                            cos90, -sin90, 0.0,
                            sin90,  cos90, 0.0,
                            0.0,    0.0,   1.0,
                        ],
                    }],
                }],
            },
            headers=headers,
        )
        client.put(f"/api/parts/ROT-ASM/A/checkin?workspace_id={_WS_ID}", headers=headers)

        r = client.get(f"/api/parts/ROT-ASM/A/instances?workspace_id={_WS_ID}", headers=headers)
        assert r.status_code == 200
        mat = np.array(r.json()[0]["matrix"]).reshape(4, 4)
        # X 轴 (1,0,0) 在 90° 旋转后变 (0,1,0)
        x_rotated = mat[:3, :3] @ np.array([1, 0, 0])
        np.testing.assert_allclose(x_rotated, [0, 1, 0], atol=1e-10)

    def test_03_conversion_status_workflow(self, client, tmp_path):
        """
        模拟完整转换流程：
          1. 创建零件并保持签出
          2. 上传 CAD 文件（mock vault + Kafka）
          3. GET .../conversion → pending=true
          4. 回调 PUT .../conversion（succeed=true）
          5. GET .../conversion → pending=false, succeed=true
        """
        headers = _login(client)

        # 创建零件（自动签出）
        client.post("/api/parts", json={
            "number": "CAD-TEST", "name": "CAD测试件", "workspaceId": str(_WS_ID),
        }, headers=headers)

        # 创建临时 vault 目录
        vault_dir = tmp_path / "vault"
        vault_dir.mkdir()

        # mock vault_path 和 Kafka 发布
        fake_stp_content = b"STEP file content for testing"

        with patch("app.crud.conversion.settings") as mock_settings, \
             patch("app.crud.conversion.publish_conversion_order", new_callable=AsyncMock):
            mock_settings.vault_path = str(vault_dir)
            mock_settings.kafka_bootstrap_servers = "kafka:9092"

            r = client.put(
                f"/api/parts/CAD-TEST/A/iterations/1/nativecad"
                f"?workspace_id={_WS_ID}&workspace_name={_WS_NAME}",
                files={"file": ("model.stp", BytesIO(fake_stp_content), "application/octet-stream")},
                headers=headers,
            )
        assert r.status_code == 200, r.text
        assert "CAD-TEST" in r.json()["fullName"]

        # 查询转换状态：应为 pending=true
        r = client.get(
            f"/api/parts/CAD-TEST/A/iterations/1/conversion?workspace_id={_WS_ID}",
            headers=headers,
        )
        assert r.status_code == 200
        assert r.json()["pending"] is True

        # conversion 回调：成功
        r = client.put(
            f"/api/parts/CAD-TEST/A/iterations/1/conversion?workspace_id={_WS_ID}",
            json={
                "succeed": True,
                "geometryFullName": f"{_WS_NAME}/parts/CAD-TEST/A/1/geometries/model.glb",
                "xMin": -10.0, "yMin": -10.0, "zMin": -10.0,
                "xMax":  10.0, "yMax":  10.0, "zMax":  10.0,
                "quality": 0,
                "contentLength": 4096,
            },
            headers=headers,
        )
        assert r.status_code == 200
        assert r.json()["succeed"] is True

        # 再查：pending=false, succeed=true
        r = client.get(
            f"/api/parts/CAD-TEST/A/iterations/1/conversion?workspace_id={_WS_ID}",
            headers=headers,
        )
        assert r.status_code == 200
        body = r.json()
        assert body["pending"] is False
        assert body["succeed"] is True

    def test_04_multiple_instances_matrix(self, client):
        """
        同一子件 3 个实例（阵列），矩阵合成接口返回 3 条结果，
        tx 值分别为 0、100、200mm。
        """
        headers = _login(client)

        client.post("/api/parts", json={
            "number": "ARRAY-LEAF", "name": "阵列件", "workspaceId": str(_WS_ID),
        }, headers=headers)
        client.put(f"/api/parts/ARRAY-LEAF/A/checkin?workspace_id={_WS_ID}", headers=headers)

        client.post("/api/parts", json={
            "number": "ARRAY-ASM", "name": "阵列装配体", "workspaceId": str(_WS_ID),
        }, headers=headers)
        client.put(
            f"/api/parts/ARRAY-ASM/A/iterations/1?workspace_id={_WS_ID}",
            json={
                "components": [{
                    "componentNumber": "ARRAY-LEAF",
                    "amount": 3,
                    "cadInstances": [
                        {"rotationType": "ANGLE", "tx": 0.0,   "ty": 0.0, "tz": 0.0, "order": 0},
                        {"rotationType": "ANGLE", "tx": 100.0, "ty": 0.0, "tz": 0.0, "order": 1},
                        {"rotationType": "ANGLE", "tx": 200.0, "ty": 0.0, "tz": 0.0, "order": 2},
                    ],
                }],
            },
            headers=headers,
        )
        client.put(f"/api/parts/ARRAY-ASM/A/checkin?workspace_id={_WS_ID}", headers=headers)

        r = client.get(f"/api/parts/ARRAY-ASM/A/instances?workspace_id={_WS_ID}", headers=headers)
        assert r.status_code == 200
        instances = r.json()
        assert len(instances) == 3

        tx_values = sorted(inst["matrix"][3] for inst in instances)
        assert tx_values == pytest.approx([0.0, 100.0, 200.0])
