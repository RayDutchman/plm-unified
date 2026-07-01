"""ECO Pydantic schema。"""
from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

def _to_camel(s: str) -> str:
    parts = s.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])

class ECOBase(BaseModel):
    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True)

class ECOCreate(ECOBase):
    title: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    reason: Optional[str] = None
    priority: str = Field("normal", max_length=32)
    category: Optional[str] = None
    ecr_id: Optional[str] = None
    reviewers: Optional[list[dict]] = None
    review_mode: str = Field("all", max_length=16)
    cc_users: Optional[list[dict]] = None
    document_links: Optional[list[dict]] = None
    release_items: Optional[list[dict]] = None
    execution_items: Optional[list[dict]] = None

class ECOExecutionItemCreate(ECOBase):
    source: str = "manual"
    entity_type: str
    entity_id: str
    entity_code: Optional[str] = None
    entity_name: Optional[str] = None
    entity_version: Optional[str] = None
    action: str = "upgrade"
    new_version: Optional[str] = None
    sort_order: int = 0

class ECOUpdate(ECOBase):
    title: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None

class ECOListParams(ECOBase):
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)
    search: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None

class ECOReviewAction(ECOBase):
    decision: str
    comment: Optional[str] = None

class ECOCcAction(ECOBase):
    user_ids: list[str]

class ECOExecutionItemAction(ECOBase):
    new_entity_id: Optional[str] = None

class ECOExecutionItemEdit(ECOBase):
    entity_name: Optional[str] = None
    action: Optional[str] = None
    entity_code: Optional[str] = None
    parent_entity_id: Optional[str] = None
    sort_order: Optional[int] = None

class ECOResponse(ECOBase):
    id: uuid.UUID
    eco_number: Optional[str] = None
    title: str
    description: Optional[str] = None
    reason: Optional[str] = None
    priority: Optional[str] = None
    category: Optional[str] = None
    status: str
    reviewers: Optional[list] = None
    review_mode: Optional[str] = None
    creator_id: Optional[uuid.UUID] = None
    ecr_id: Optional[uuid.UUID] = None
    ecr_number: Optional[str] = None
    document_links: Optional[list] = None
    cc_users: Optional[list] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    executed_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    execution_count: int = 0
    execution_completed_count: int = 0
    creator_name: Optional[str] = None
