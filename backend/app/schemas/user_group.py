"""用户组 Pydantic 模式。"""
from __future__ import annotations

import uuid
from typing import Optional, List

from pydantic import BaseModel, ConfigDict, Field


class UserGroupCreate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str = Field(..., min_length=1, max_length=64)
    description: Optional[str] = None


class UserGroupUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: Optional[str] = None
    description: Optional[str] = None


class GroupMembersUpdate(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    user_ids: List[uuid.UUID] = []


class UserGroupsUpdate(BaseModel):
    """设置某个用户所属的用户组。"""
    model_config = ConfigDict(from_attributes=True)
    group_ids: List[uuid.UUID] = []
