"""登录用户。对应 DocDoku User，新增 workspace_id 归属。"""
import uuid
from sqlalchemy import Column, String, Uuid, ForeignKey
from app.database import Base
from app.models.mixins import TimestampMixin, SoftDeleteMixin


class User(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "users"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(Uuid(as_uuid=True), ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False)
    username = Column(String(64), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    real_name = Column(String(64), nullable=False)
    role = Column(String(32), nullable=False)
    department = Column(String(128), nullable=True)
    phone = Column(String(32), nullable=True)
    status = Column(String(32), nullable=False, default="active")
