"""图文档 Pydantic schema。"""
from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field


def _to_camel(s: str) -> str:
    parts = s.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


class DocumentCreate(BaseModel):
    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True)
    code: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=255)
    remark: Optional[str] = None
    group_ids: Optional[List[uuid.UUID]] = None


class DocumentUpdate(BaseModel):
    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True)
    code: Optional[str] = None
    name: Optional[str] = None
    status: Optional[str] = None
    remark: Optional[str] = None
    group_ids: Optional[List[uuid.UUID]] = None


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, alias_generator=_to_camel, populate_by_name=True)
    id: uuid.UUID
    code: str
    name: str
    version: str
    status: str
    remark: Optional[str] = None
    file_name: Optional[str] = None
    file_id: Optional[uuid.UUID] = None
    creator_id: uuid.UUID
    created_at: datetime
    updated_at: datetime


class DocumentAttachmentCreate(BaseModel):
    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True)
    id: Optional[uuid.UUID] = None
    file_name: str
    file_data: str


class UpgradeRequest(BaseModel):
    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True)
    note: Optional[str] = None
