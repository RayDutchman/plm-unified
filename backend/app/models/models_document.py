"""图文档模型。"""
import uuid
from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, String, Text, Uuid, func
from app.database import Base
from app.models.mixins import TimestampMixin, SoftDeleteMixin


class Document(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "documents"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(64), nullable=False)
    name = Column(String(255), nullable=False)
    version = Column(String(10), nullable=False, default="A")
    status = Column(String(32), nullable=False, default="draft")
    remark = Column(Text, nullable=True)
    file_name = Column(String(500), nullable=True)
    file_id = Column(Uuid(as_uuid=True), ForeignKey("document_attachments.id", ondelete="SET NULL"), nullable=True)
    creator_id = Column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)


class DocumentAttachment(Base, TimestampMixin):
    __tablename__ = "document_attachments"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(Uuid(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    file_name = Column(String(500), nullable=False)
    file_size = Column(BigInteger, nullable=False, default=0)
    file_path = Column(String(1000), nullable=False)
    file_hash = Column(String(64), nullable=True)


class DocumentLink(Base):
    __tablename__ = "document_links"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(Uuid(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    entity_type = Column(String(32), nullable=False)
    entity_id = Column(Uuid(as_uuid=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class DocumentGroupLink(Base):
    __tablename__ = "document_group_links"

    document_id = Column(Uuid(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), primary_key=True)
    group_id = Column(Uuid(as_uuid=True), ForeignKey("user_groups.id", ondelete="CASCADE"), primary_key=True)
