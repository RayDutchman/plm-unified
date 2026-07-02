"""
ChangeIssue - SQLAlchemy Model
==============================
变更管理 - 问题报告模块数据模型
"""

import uuid
from sqlalchemy import Column, String, Integer, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.database import Base


class ChangeIssue(Base):
    """问题报告 —— 变更流程的起点，可生成一个或多个 ECR"""

    __tablename__ = "change_issues"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    issue_number = Column(String(32), unique=True, nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # 问题来源（客户投诉、质检发现、CATIA 反馈 等）
    initiator = Column(String(128), nullable=True)

    priority = Column(String(16), nullable=False, default="normal")
    category = Column(String(32), nullable=True)
    status = Column(String(16), nullable=False, default="open")

    # 经办人 / 创建人
    assignee_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    author_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    # 所属工作空间
    workspace_id = Column(UUID(as_uuid=True), ForeignKey("workspaces.id"), nullable=False)

    # 标签、关联件
    tags = Column(JSONB, nullable=False, default=[])
    affected_parts = Column(JSONB, nullable=False, default=[])
    affected_documents = Column(JSONB, nullable=False, default=[])

    # 知会用户
    cc_users = Column(JSONB, nullable=False, default=[])

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    resolved_at = Column(DateTime(timezone=True), nullable=True)
    closed_at = Column(DateTime(timezone=True), nullable=True)
    deleted_at = Column(DateTime(timezone=True), nullable=True, default=None)
