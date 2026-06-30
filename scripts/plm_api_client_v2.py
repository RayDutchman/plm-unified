"""
plm-unified FastAPI 后端的 API 客户端。

2.9 sync.py 适配：
  - 认证改为 JWT（POST /api/auth/token 获取 Bearer token）
  - base_url 改为新 FastAPI 后端
  - API 路径和响应格式对应新接口

用法：
    from scripts.plm_api_client_v2 import PlmApiClientV2

    client = PlmApiClientV2(
        base_url="http://localhost:8010",
        username="admin",
        password="your_password",
        workspace_id="00000000-0000-0000-0000-000000000001",
    )
    client.login()  # 获取 JWT，后续请求自动携带

    # 与 sync.py 兼容的接口
    part = client.get_part_head("Workspace_0", "PART-001")
    client.create_part("Workspace_0", "PART-001", "零件名称")
    client.checkout_part("Workspace_0", "PART-001", "A")
    client.checkin_part("Workspace_0", "PART-001", "A")
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Optional

import requests

logger = logging.getLogger(__name__)


class PlmApiError(Exception):
    """API 调用错误。"""
    def __init__(self, message: str, status_code: int = 0):
        super().__init__(message)
        self.status_code = status_code


class PlmApiClientV2:
    """
    plm-unified FastAPI 后端的 HTTP 客户端。
    接口与旧 PlmApiClient 保持兼容，供 sync.py 无缝替换。
    """

    def __init__(
        self,
        base_url: str,
        username: str,
        password: str,
        workspace_id: str | uuid.UUID,
        timeout: int = 30,
    ):
        self.base_url = base_url.rstrip("/")
        self._username = username
        self._password = password
        self._workspace_id = str(workspace_id)
        self._timeout = timeout
        self._login = username  # sync.py 中用于比较签出人

        self._session = requests.Session()
        self._access_token: Optional[str] = None

    # ──────────────────────────────────────────────────────────────────────
    # 认证
    # ──────────────────────────────────────────────────────────────────────

    def login(self) -> None:
        """登录获取 JWT access_token，后续请求自动携带 Authorization: Bearer。"""
        resp = requests.post(
            f"{self.base_url}/api/auth/token",
            data={"username": self._username, "password": self._password},
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=self._timeout,
        )
        if resp.status_code != 200:
            raise PlmApiError(f"登录失败：{resp.text}", resp.status_code)

        body = resp.json()
        self._access_token = body["access_token"]
        self._session.headers.update({"Authorization": f"Bearer {self._access_token}"})
        logger.info("已登录为 %s", self._username)

    def _ensure_logged_in(self) -> None:
        if not self._access_token:
            self.login()

    def _get(self, path: str, **params) -> Any:
        self._ensure_logged_in()
        resp = self._session.get(
            f"{self.base_url}{path}", params=params, timeout=self._timeout
        )
        if resp.status_code >= 400:
            raise PlmApiError(f"GET {path} 失败 ({resp.status_code}): {resp.text}", resp.status_code)
        return resp.json()

    def _post(self, path: str, json: Any = None, **params) -> Any:
        self._ensure_logged_in()
        resp = self._session.post(
            f"{self.base_url}{path}", json=json, params=params, timeout=self._timeout
        )
        if resp.status_code >= 400:
            raise PlmApiError(f"POST {path} 失败 ({resp.status_code}): {resp.text}", resp.status_code)
        return resp.json()

    def _put(self, path: str, json: Any = None, **params) -> Any:
        self._ensure_logged_in()
        resp = self._session.put(
            f"{self.base_url}{path}", json=json, params=params, timeout=self._timeout
        )
        if resp.status_code >= 400:
            raise PlmApiError(f"PUT {path} 失败 ({resp.status_code}): {resp.text}", resp.status_code)
        return resp.json()

    # ──────────────────────────────────────────────────────────────────────
    # 零件 CRUD（对应 M1 接口）
    # ──────────────────────────────────────────────────────────────────────

    def get_part_head(self, workspace: str, part_number: str) -> dict:
        """
        获取零件头信息（最新版本签出状态）。
        返回 dict 与旧 DocDoku 格式兼容（checkOutUser/status/lastIterationNumber）。
        """
        data = self._get(
            f"/api/parts/{part_number}",
            workspace_id=self._workspace_id,
        )
        # 转换为 sync.py 期望的旧格式
        revisions = data.get("revisions", [])
        latest_rev = revisions[-1] if revisions else {}
        iterations = latest_rev.get("iterations", [])

        return {
            "number": data["number"],
            "name": data["name"],
            "version": latest_rev.get("version", "A"),
            "lastIterationNumber": len(iterations),
            "status": latest_rev.get("status", "WIP"),
            "checkOutUser": (
                {"login": latest_rev.get("checkoutUserId")}
                if latest_rev.get("checkoutUserId") else None
            ),
            "checkOutDate": latest_rev.get("checkoutDate"),
            # 供 sync.py 兼容
            "_raw": data,
        }

    def get_latest_version(self, workspace: str, part_number: str) -> tuple[str, int]:
        """返回 (version, iteration)，供 sync.py 判断最新版本。"""
        data = self._get(f"/api/parts/{part_number}", workspace_id=self._workspace_id)
        revisions = data.get("revisions", [])
        if not revisions:
            raise PlmApiError(f"零件 {part_number} 无版本", 404)
        latest_rev = revisions[-1]
        iterations = latest_rev.get("iterations", [])
        return latest_rev["version"], len(iterations)

    def list_parts(self, workspace: str) -> list[dict]:
        """列出工作空间内所有零件。"""
        return self._get("/api/parts", workspace_id=self._workspace_id, limit=200)

    def create_part(self, workspace: str, part_number: str, name: str, **kwargs) -> dict:
        """
        创建零件（三层原子事务：master + revision A + iteration 1）。
        创建后自动签出，无需单独调用 checkout。
        """
        return self._post("/api/parts", json={
            "number": part_number,
            "name": name,
            "workspaceId": self._workspace_id,
            **kwargs,
        })

    def checkout_part(self, workspace: str, part_number: str, version: str) -> dict:
        """签出零件版本。"""
        return self._put(
            f"/api/parts/{part_number}/{version}/checkout",
            workspace_id=self._workspace_id,
        )

    def checkin_part(
        self,
        workspace: str,
        part_number: str,
        version: str,
        iteration_note: str = "",
    ) -> dict:
        """签入零件版本。"""
        params = {"workspace_id": self._workspace_id}
        if iteration_note:
            params["iteration_note"] = iteration_note
        return self._put(f"/api/parts/{part_number}/{version}/checkin", **params)

    def undo_checkout_part(self, workspace: str, part_number: str, version: str) -> dict:
        """撤销签出。"""
        return self._put(
            f"/api/parts/{part_number}/{version}/undocheckout",
            workspace_id=self._workspace_id,
        )

    def force_undo_checkout(self, workspace: str, part_number: str, version: str) -> dict:
        """
        强制撤销他人签出（M1 未实现，降级为记录 warning）。
        与旧 api_client 保持接口兼容，实际效果同 skip。
        """
        logger.warning(
            "force_undo_checkout: 新 FastAPI 后端 M1 不支持强制撤销他人签出，已跳过 %s/%s",
            part_number, version,
        )
        raise PlmApiError("不支持强制撤销他人签出", 501)

    def delete_part(self, workspace: str, part_number: str, version: str) -> None:
        """删除零件版本（M1 未实现，占位）。"""
        raise PlmApiError("delete_part 尚未在新后端实现", 501)

    # ──────────────────────────────────────────────────────────────────────
    # 迭代内容（对应 M2 接口）
    # ──────────────────────────────────────────────────────────────────────

    def update_iteration(
        self,
        workspace: str,
        part_number: str,
        version: str,
        iteration: int,
        components: list[dict] | None = None,
        iteration_note: str = "",
        **kwargs,
    ) -> dict:
        """
        更新迭代内容（BOM + 位置信息）。
        components 格式：[{"componentNumber": str, "cadInstances": [...], ...}]
        """
        body = {"iterationNote": iteration_note}
        if components:
            body["components"] = [
                {
                    "componentNumber": c.get("componentNumber") or c.get("component", {}).get("number"),
                    "amount": c.get("amount", 1.0),
                    "unit": c.get("unit"),
                    "optional": c.get("optional", False),
                    "order": c.get("order", 0),
                    "comment": c.get("comment"),
                    "cadInstances": c.get("cadInstances", []),
                }
                for c in components
            ]
        return self._put(
            f"/api/parts/{part_number}/{version}/iterations/{iteration}",
            json=body,
            workspace_id=self._workspace_id,
        )

    def upload_step(
        self,
        workspace: str,
        part_number: str,
        version: str,
        iteration: int,
        file_path: str,
    ) -> dict:
        """上传 STP 文件到 vault，触发 Kafka 转换。"""
        self._ensure_logged_in()
        with open(file_path, "rb") as f:
            resp = self._session.put(
                f"{self.base_url}/api/parts/{part_number}/{version}/iterations/{iteration}/nativecad",
                files={"file": (f.name.split("/")[-1], f)},
                params={
                    "workspace_id": self._workspace_id,
                    "workspace_name": workspace,
                },
                timeout=120,  # 上传可能较慢
            )
        if resp.status_code >= 400:
            raise PlmApiError(f"上传 STP 失败: {resp.text}", resp.status_code)
        return resp.json()

    def get_conversion_status(
        self,
        workspace: str,
        part_number: str,
        version: str,
        iteration: int,
    ) -> dict:
        """
        查询转换状态。返回 {pending, succeed, startDate, endDate}。
        sync.py 会轮询此接口直到 pending=False。
        """
        return self._get(
            f"/api/parts/{part_number}/{version}/iterations/{iteration}/conversion",
            workspace_id=self._workspace_id,
        )

    def upload_attached_file(
        self,
        workspace: str,
        part_number: str,
        version: str,
        iteration: int,
        file_path: str,
    ) -> dict:
        """上传附件（M2 未实现，占位）。"""
        raise PlmApiError("upload_attached_file 尚未在新后端实现", 501)

    def ensure_part_template(self, workspace: str) -> Optional[str]:
        """零件模板（新后端不需要），返回 None 兼容旧调用。"""
        return None

    def create_product(self, workspace: str, *args, **kwargs) -> None:
        """ConfigurationItem（M2 不实现）。"""
        pass
