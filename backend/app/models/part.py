"""零件三层模型。对应 DocDoku PartMaster / PartRevision / PartIteration。"""
import uuid
from sqlalchemy import (
    Column, String, Text, Integer, Boolean, Uuid, ForeignKey, DateTime,
    UniqueConstraint, CheckConstraint, Index, func,
)
from sqlalchemy.dialects.postgresql import JSONB
from app.database import Base
from app.models.mixins import TimestampMixin, SoftDeleteMixin


class PartMaster(Base, TimestampMixin, SoftDeleteMixin):
    """零件主数据。workspace_id + number 唯一。"""
    __tablename__ = "part_masters"
    __table_args__ = (
        UniqueConstraint("workspace_id", "number", name="uq_part_master_ws_number"),
        Index("idx_part_masters_workspace", "workspace_id"),
        Index("idx_part_masters_number", "number"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(Uuid(as_uuid=True), ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False)
    number = Column(String(100), nullable=False)
    name = Column(String(255), nullable=False)
    type = Column(String(50), nullable=True)
    standard_part = Column(Boolean, nullable=False, default=False)
    author_id = Column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    document_links = Column(JSONB, default=[])


class PartRevision(Base, TimestampMixin, SoftDeleteMixin):
    """零件版本（A/B/C…）。状态机 WIP→RELEASED→OBSOLETE。"""
    __tablename__ = "part_revisions"
    __table_args__ = (
        UniqueConstraint("part_master_id", "version", name="uq_part_revision_master_version"),
        CheckConstraint("status IN ('WIP','RELEASED','OBSOLETE')", name="ck_part_revision_status"),
        Index("idx_part_revisions_master", "part_master_id"),
        Index("idx_part_revisions_checkout", "checkout_user_id"),
        Index("idx_part_revisions_status", "status"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    part_master_id = Column(Uuid(as_uuid=True), ForeignKey("part_masters.id", ondelete="CASCADE"), nullable=False)
    version = Column(String(10), nullable=False)
    status = Column(String(20), nullable=False, default="WIP")
    description = Column(Text, nullable=True)
    # 签出锁：非空表示已被该用户签出
    checkout_user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    checkout_date = Column(DateTime(timezone=True), nullable=True)
    released_by_id = Column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    released_at = Column(DateTime(timezone=True), nullable=True)
    obsoleted_by_id = Column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    obsoleted_at = Column(DateTime(timezone=True), nullable=True)


class PartIteration(Base, TimestampMixin):
    """零件迭代（1/2/3…）。签入后 check_in_date 非空即冻结。"""
    __tablename__ = "part_iterations"
    __table_args__ = (
        UniqueConstraint("part_revision_id", "iteration", name="uq_part_iteration_revision_iter"),
        CheckConstraint("iteration > 0", name="ck_part_iteration_positive"),
        Index("idx_part_iterations_revision", "part_revision_id"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    part_revision_id = Column(Uuid(as_uuid=True), ForeignKey("part_revisions.id", ondelete="CASCADE"), nullable=False)
    iteration = Column(Integer, nullable=False)
    iteration_note = Column(Text, nullable=True)
    native_cad_file_id = Column(Uuid(as_uuid=True), ForeignKey("binary_resources.id", ondelete="SET NULL"), nullable=True)
    check_in_date = Column(DateTime(timezone=True), nullable=True)
    author_id = Column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
