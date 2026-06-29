"""二进制资源与几何体。对应 DocDoku BinaryResource / Geometry。"""
import uuid
from sqlalchemy import (
    Column, String, BigInteger, Integer, Double, Uuid, ForeignKey, DateTime, func,
)
from app.database import Base


class BinaryResource(Base):
    """文件元数据，实际文件在 vault。full_name 为全局唯一路径键。"""
    __tablename__ = "binary_resources"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    full_name = Column(String(500), nullable=False, unique=True)
    content_length = Column(BigInteger, nullable=False, default=0)
    last_modified = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Geometry(Base):
    """迭代的 LOD 几何体，含包围盒（毫米）。"""
    __tablename__ = "geometries"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    iteration_id = Column(Uuid(as_uuid=True), ForeignKey("part_iterations.id", ondelete="CASCADE"), nullable=False)
    binary_resource_id = Column(Uuid(as_uuid=True), ForeignKey("binary_resources.id", ondelete="RESTRICT"), nullable=False)
    quality = Column(Integer, nullable=False, default=0)  # 0=最高 LOD
    x_min = Column(Double, nullable=False)
    y_min = Column(Double, nullable=False)
    z_min = Column(Double, nullable=False)
    x_max = Column(Double, nullable=False)
    y_max = Column(Double, nullable=False)
    z_max = Column(Double, nullable=False)
