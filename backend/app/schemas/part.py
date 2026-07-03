"""零件相关 Pydantic schema。

命名约定：
  - Request  schema 后缀 Create / Update
  - Response schema 后缀 Response
  - 字段使用 snake_case；alias 提供 camelCase 供前端 JSON 消费
  - populate_by_name=True：后端内部可用 snake_case 构造，前端可用 camelCase 传参

camelCase alias 策略：仅对含下划线的复合字段名加 alias，单词字段不重复定义。
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


def _to_camel(s: str) -> str:
    """snake_case → camelCase 转换器，注册到 alias_generator。"""
    parts = s.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


# ---------------------------------------------------------------------------
# 通用配置基类
# ---------------------------------------------------------------------------

class _OrmBase(BaseModel):
    """ORM 对象直接构造 + camelCase alias 输出 + snake_case 内部访问。"""
    model_config = ConfigDict(
        from_attributes=True,       # 允许从 SQLAlchemy ORM 对象直接构造
        alias_generator=_to_camel,  # 自动为所有字段生成 camelCase alias
        populate_by_name=True,      # 同时接受 snake_case 和 camelCase 输入
    )


class _RequestBase(BaseModel):
    """请求体基类：camelCase 输入 + snake_case 内部访问。"""
    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
    )


# ---------------------------------------------------------------------------
# PartIteration（迭代）
# ---------------------------------------------------------------------------

class IterationResponse(_OrmBase):
    """零件迭代信息。check_in_date 非空 = 已冻结（签入完成）。"""
    id: uuid.UUID
    iteration: int
    iteration_note: Optional[str] = None
    native_cad_file_id: Optional[uuid.UUID] = None
    check_in_date: Optional[datetime] = None
    author_id: uuid.UUID
    created_at: datetime


# ---------------------------------------------------------------------------
# PartRevision（版本）
# ---------------------------------------------------------------------------

class RevisionResponse(_OrmBase):
    """零件版本信息。checkout_user_id 非空 = 已被签出。"""
    id: uuid.UUID
    version: str
    status: str
    description: Optional[str] = None
    checkout_user_id: Optional[uuid.UUID] = None
    checkout_date: Optional[datetime] = None
    created_at: datetime
    iterations: list[IterationResponse] = []


# ---------------------------------------------------------------------------
# PartMaster（主数据）
# ---------------------------------------------------------------------------

class PartCreate(_RequestBase):
    """创建零件请求体。number/name 不允许空字符串或过长字符串。"""
    number: str = Field(..., min_length=1, max_length=100, description="零件编号，工作空间内唯一")
    name: str = Field(..., min_length=1, max_length=255, description="零件名称")
    workspace_id: uuid.UUID = Field(..., description="所属工作空间 ID")
    type: Optional[str] = Field(None, max_length=50, description="零件类型（可选分类）")
    standard_part: bool = Field(False, description="是否标准件（外购/通用件）")
    description: Optional[str] = Field(None, description="首个版本的描述（可选）")


class UsageLinkBriefSchema(BaseModel):
    component_number: str = ""
    component_name: str = ""
    amount: float = 1.0
    unit: Optional[str] = None

    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True)


class PartResponse(_OrmBase):
    """零件完整信息，含所有版本和迭代。"""
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
    latest_version: Optional[str] = None
    latest_status: Optional[str] = None
    checkout_user_id: Optional[uuid.UUID] = None
    is_assembly: bool = False
    child_count: int = 0
    usage_links: list[UsageLinkBriefSchema] = []


class PartListItem(_OrmBase):
    """零件列表条目（精简，不含迭代详情）。"""
    id: uuid.UUID
    workspace_id: uuid.UUID
    number: str
    name: str
    type: Optional[str] = None
    standard_part: bool
    author_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    # 最新版本的签出状态（由 router 层手动填充）
    latest_version: Optional[str] = None
    latest_status: Optional[str] = None
    checkout_user_id: Optional[uuid.UUID] = None


# ---------------------------------------------------------------------------
# 签入签出操作 Response
# ---------------------------------------------------------------------------

class CheckoutResponse(BaseModel):
    """checkout / checkin / undocheckout 操作的统一响应体。"""
    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True)

    number: str = Field(..., description="零件编号")
    version: str = Field(..., description="操作的版本号")
    status: str = Field(..., description="操作后的版本状态")
    checkout_user_id: Optional[uuid.UUID] = Field(None, description="当前签出用户 ID，NULL 表示未签出")
    checkout_date: Optional[datetime] = Field(None, description="签出时间")
    message: str = Field(..., description="操作结果描述")
