"""myPDM 零部件业务模型（图文档已有 models_document 提供）。"""
import uuid
from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.database import Base
from app.models.mixins import TimestampMixin, SoftDeleteMixin


class Component(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "components"
    __table_args__ = ()

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(64), nullable=False)
    name = Column(String(255), nullable=False)
    spec = Column(String(255))
    version = Column(String(32), default="A")
    status = Column(String(32), nullable=False, default="draft")
    remark = Column(Text)
    revisions = Column(JSONB, default=[])
    revision_parent_id = Column(UUID(as_uuid=True), nullable=True)
    creator_id = Column(UUID(as_uuid=True), nullable=True)
    document_links = Column(JSONB, default=[])


class ComponentAttachment(Base):
    __tablename__ = "component_attachments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    part_master_id = Column(UUID(as_uuid=True), ForeignKey("part_masters.id", ondelete="CASCADE"), nullable=False)
    category = Column(String(32), nullable=False)
    file_name = Column(String(255))
    file_size = Column(Integer)
    file_path = Column(String(512))
    file_hash = Column(String(64))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
