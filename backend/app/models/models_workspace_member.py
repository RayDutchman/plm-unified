"""WorkspaceMember - 工作区成员关系（多对多）"""
import uuid
from sqlalchemy import Column, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy import DateTime
from app.database import Base


class WorkspaceMember(Base):
    """工作区成员表 —— 用户可访问的工作区（多对多）"""

    __tablename__ = "workspace_members"

    workspace_id = Column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    user_id = Column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    joined_at = Column(DateTime(timezone=True), server_default=func.now())
