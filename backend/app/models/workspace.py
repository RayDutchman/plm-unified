"""工作空间。对应 DocDoku Workspace。"""
import uuid
from sqlalchemy import Column, String, Text, Uuid
from app.database import Base
from app.models.mixins import TimestampMixin, SoftDeleteMixin


class Workspace(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "workspaces"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, unique=True)  # 工作空间标识
    description = Column(Text, nullable=True)
