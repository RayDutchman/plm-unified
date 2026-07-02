"""ChangeIssue Pydantic schema。"""
from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


def _to_camel(s: str) -> str:
    parts = s.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


class IssueBase(BaseModel):
    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True, from_attributes=True)


class IssueCreate(IssueBase):
    title: str = Field(..., max_length=255)
    description: Optional[str] = None
    initiator: Optional[str] = None
    priority: str = Field("normal")
    category: Optional[str] = None
    assignee_id: Optional[uuid.UUID] = None
    tags: list[str] = []
    affected_parts: list[dict] = []
    affected_documents: list[dict] = []
    cc_users: list[dict] = []


class IssueUpdate(IssueBase):
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    initiator: Optional[str] = None
    priority: Optional[str] = None
    category: Optional[str] = None
    status: Optional[str] = None
    assignee_id: Optional[uuid.UUID] = None
    tags: Optional[list[str]] = None
    affected_parts: Optional[list[dict]] = None
    affected_documents: Optional[list[dict]] = None
    cc_users: Optional[list[dict]] = None


class IssueResponse(IssueBase):
    id: uuid.UUID
    issue_number: str
    title: str
    description: Optional[str] = None
    initiator: Optional[str] = None
    priority: str
    category: Optional[str] = None
    status: str
    assignee_id: Optional[uuid.UUID] = None
    author_id: uuid.UUID
    workspace_id: uuid.UUID
    tags: list = []
    affected_parts: list = []
    affected_documents: list = []
    cc_users: list = []
    created_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None


class IssueListResponse(IssueBase):
    items: list[IssueResponse]
    total: int
    page: int
    page_size: int
