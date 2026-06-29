"""用户请求/响应 schema。"""
import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)  # 支持从 ORM 对象构造
    id: uuid.UUID
    workspace_id: uuid.UUID
    username: str
    real_name: str
    role: str
    department: Optional[str] = None
    phone: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime


class UserCreate(BaseModel):
    workspace_id: uuid.UUID
    username: str = Field(..., min_length=3, max_length=64)
    password: str = Field(..., min_length=6)
    real_name: str = Field(..., min_length=1, max_length=64)
    role: str
    department: Optional[str] = None
    phone: Optional[str] = None
    status: str = "active"
