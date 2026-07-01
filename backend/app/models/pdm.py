"""myPDM 零部件业务模型（图文档已有 models_document 提供）。"""
import uuid
from sqlalchemy import Column, String, Integer, DateTime, Uuid as SA_Uuid, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.database import Base


class PartAttachment(Base):
    __tablename__ = "part_attachments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    part_master_id = Column(UUID(as_uuid=True), ForeignKey("part_masters.id", ondelete="CASCADE"), nullable=False)
    category = Column(String(32), nullable=False)
    file_name = Column(String(255))
    file_size = Column(Integer)
    file_path = Column(String(512))
    file_hash = Column(String(64))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
