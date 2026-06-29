"""零件相关 Pydantic schema。

命名约定：
  - Request  schema 后缀 Create / Update
  - Response schema 后缀 Response
  - 字段使用 snake_case（FastAPI 默认，前端适配由 camelCase alias 处理）
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# 通用配置：允许从 ORM 对象直接构造（from_attributes）
# ---------------------------------------------------------------------------

class _OrmBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# PartIteration
# ---------------------------------------------------------------------------

class IterationResponse(_OrmBase):
    id: uuid.UUID
    iteration: int
    iteration_note: Optional[str] = None
    native_cad_file_id: Optional[uuid.UUID] = None
    check_in_date: Optional[datetime] = None
    author_id: uuid.UUID
    created_at: datetime


# ---------------------------------------------------------------------------
# PartRevision
# ---------------------------------------------------------------------------

class RevisionResponse(_OrmBase):
    id: uuid.UUID
    version: str
    status: str
    description: Optional[str] = None
    checkout_user_id: Optional[uuid.UUID] = None
    checkout_date: Optional[datetime] = None
    created_at: datetime
    iterations: list[IterationResponse] = []


# ---------------------------------------------------------------------------
# PartMaster
# ---------------------------------------------------------------------------

class PartCreate(BaseModel):
    """创建零件请求体。"""
    number: str
    name: str
    workspace_id: uuid.UUID
    type: Optional[str] = None
    standard_part: bool = False
    description: Optional[str] = None  # 首个 Revision 的描述


class PartResponse(_OrmBase):
    id: uuid.UUID
    workspace_id: uuid.UUID
    number: str
    name: str
    type: Optional[str] = None
    standard_part: bool
    author_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None
    revisions: list[RevisionResponse] = []


class PartListItem(_OrmBase):
    """列表接口返回的精简零件信息（不含迭代详情）。"""
    id: uuid.UUID
    workspace_id: uuid.UUID
    number: str
    name: str
    type: Optional[str] = None
    standard_part: bool
    author_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    # 最新版本的简要状态
    latest_version: Optional[str] = None
    latest_status: Optional[str] = None
    checkout_user_id: Optional[uuid.UUID] = None


# ---------------------------------------------------------------------------
# 签入签出 Response
# ---------------------------------------------------------------------------

class CheckoutResponse(BaseModel):
    """签出/签入/撤销签出操作的统一响应体。"""
    number: str
    version: str
    status: str
    checkout_user_id: Optional[uuid.UUID] = None
    checkout_date: Optional[datetime] = None
    message: str
