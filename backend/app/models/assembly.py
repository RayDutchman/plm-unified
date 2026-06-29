"""装配关系。对应 DocDoku PartUsageLink / CADInstance。"""
import uuid
from sqlalchemy import (
    Column, String, Text, Integer, Boolean, Double, Uuid, ForeignKey, CheckConstraint,
)
from app.database import Base


class PartUsageLink(Base):
    """父迭代使用子零件（BOM）。子件引用 part_masters（非具体版本）。"""
    __tablename__ = "part_usage_links"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    parent_iteration_id = Column(Uuid(as_uuid=True), ForeignKey("part_iterations.id", ondelete="CASCADE"), nullable=False)
    component_master_id = Column(Uuid(as_uuid=True), ForeignKey("part_masters.id", ondelete="RESTRICT"), nullable=False)
    amount = Column(Double, nullable=False, default=1.0)
    unit = Column(String(20), nullable=True)
    optional = Column(Boolean, nullable=False, default=False)
    # "order" 是 SQL 保留字，SQLAlchemy 自动加引号
    order = Column("order", Integer, nullable=False, default=0)
    comment = Column(Text, nullable=True)


class CADInstance(Base):
    """子件在父装配中的一次位置实例。ANGLE=欧拉角 / MATRIX=3x3 旋转矩阵。"""
    __tablename__ = "cad_instances"
    __table_args__ = (
        CheckConstraint("rotation_type IN ('ANGLE','MATRIX')", name="ck_cad_instance_rotation_type"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    usage_link_id = Column(Uuid(as_uuid=True), ForeignKey("part_usage_links.id", ondelete="CASCADE"), nullable=False)
    tx = Column(Double, nullable=False, default=0.0)
    ty = Column(Double, nullable=False, default=0.0)
    tz = Column(Double, nullable=False, default=0.0)
    rotation_type = Column(String(10), nullable=False)
    # ANGLE 模式：欧拉角（弧度）
    rx = Column(Double, nullable=True)
    ry = Column(Double, nullable=True)
    rz = Column(Double, nullable=True)
    # MATRIX 模式：3x3 旋转矩阵（列优先）
    m00 = Column(Double, nullable=True); m01 = Column(Double, nullable=True); m02 = Column(Double, nullable=True)
    m10 = Column(Double, nullable=True); m11 = Column(Double, nullable=True); m12 = Column(Double, nullable=True)
    m20 = Column(Double, nullable=True); m21 = Column(Double, nullable=True); m22 = Column(Double, nullable=True)
    order = Column("order", Integer, nullable=False, default=0)
