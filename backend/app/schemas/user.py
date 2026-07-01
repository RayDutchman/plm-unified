"""用户相关 Pydantic schema。"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


def _to_camel(s: str) -> str:
    parts = s.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


class UserCreate(BaseModel):
    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True)
    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=6, max_length=128)
    real_name: str = Field(..., min_length=1, max_length=64)
    role: str = Field("engineer", max_length=32)
    department: Optional[str] = Field(None, max_length=128)
    phone: Optional[str] = Field(None, max_length=32)
    workspace_id: Optional[uuid.UUID] = None


class UserUpdate(BaseModel):
    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True)
    username: Optional[str] = Field(None, min_length=1, max_length=64)
    real_name: Optional[str] = Field(None, min_length=1, max_length=64)
    role: Optional[str] = Field(None, max_length=32)
    department: Optional[str] = Field(None, max_length=128)
    phone: Optional[str] = Field(None, max_length=32)
    status: Optional[str] = Field(None, max_length=32)


class UserResponse(BaseModel):
    # 前端用户管理 / 审批人·抄送选择等均按 snake_case 读取用户字段（real_name、created_at 等），
    # 故响应不启用 camelCase alias，保持 snake_case 输出与前端一致。
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    workspace_id: Optional[uuid.UUID] = None
    username: str
    real_name: str
    role: str
    department: Optional[str] = None
    phone: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime
