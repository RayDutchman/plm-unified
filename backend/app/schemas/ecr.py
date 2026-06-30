"""ECR Pydantic schema。"""
from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


def _to_camel(s: str) -> str:
    parts = s.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


class ECRBase(BaseModel):
    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True)


class ECRDocumentLinkItem(ECRBase):
    document_id: str
    document_code: str
    document_name: str
    document_version: str


class ECRReviewerItem(ECRBase):
    user_id: str
    seq: int = 0


class ECRCreate(ECRBase):
    title: str = Field(..., max_length=255)
    description: Optional[str] = None
    reason: str
    priority: str = Field("normal")
    category: Optional[str] = None
    reviewers: list[ECRReviewerItem] = []
    review_mode: str = Field("all", max_length=16)
    document_links: list[ECRDocumentLinkItem] = []


class ECRUpdate(ECRBase):
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    reason: Optional[str] = None
    priority: Optional[str] = None
    category: Optional[str] = None
    reviewers: Optional[list[ECRReviewerItem]] = None
    review_mode: Optional[str] = None
    document_links: Optional[list[ECRDocumentLinkItem]] = None


class ECRListParams(ECRBase):
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)
    search: Optional[str] = None
    status: Optional[str] = None
    priority: Optional[str] = None


class ECRReviewAction(ECRBase):
    decision: str
    comment: Optional[str] = None


class ECRCloseAction(ECRBase):
    comment: Optional[str] = None


class ECRAffectedItemCreate(ECRBase):
    entity_type: str
    entity_id: str
    change_description: Optional[str] = None
    change_type: Optional[str] = None


class ECRResponse(ECRBase):
    model_config = ConfigDict(from_attributes=True, alias_generator=_to_camel, populate_by_name=True)
    id: uuid.UUID
    ecr_number: Optional[str] = None
    title: str
    description: Optional[str] = None
    reason: Optional[str] = None
    priority: Optional[str] = None
    category: Optional[str] = None
    status: str
    reviewers: Optional[list] = None
    review_mode: Optional[str] = None
    creator_id: Optional[uuid.UUID] = None
    document_links: Optional[list] = None
    cc_users: Optional[list] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    reviewed_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    eco_id: Optional[uuid.UUID] = None
    affected_count: int = 0
    reviewers_count: int = 0
    approved_count: int = 0
    creator_name: Optional[str] = None
