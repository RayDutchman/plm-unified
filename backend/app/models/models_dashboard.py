"""仪表盘/看板模型。"""
import uuid
from sqlalchemy import Column, String, Integer, Uuid, ForeignKey, UniqueConstraint
from app.database import Base
from app.models.mixins import TimestampMixin


class UserDashboard(Base, TimestampMixin):
    __tablename__ = "user_dashboards"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    name = Column(String(128), nullable=False, default="我的看板")


class DashboardFolder(Base, TimestampMixin):
    __tablename__ = "dashboard_folders"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dashboard_id = Column(Uuid(as_uuid=True), ForeignKey("user_dashboards.id", ondelete="CASCADE"), nullable=False)
    parent_id = Column(Uuid(as_uuid=True), ForeignKey("dashboard_folders.id", ondelete="CASCADE"), nullable=True)
    name = Column(String(128), nullable=False)
    sort_order = Column(Integer, nullable=False, default=0)


class DashboardItem(Base, TimestampMixin):
    __tablename__ = "dashboard_items"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    folder_id = Column(Uuid(as_uuid=True), ForeignKey("dashboard_folders.id", ondelete="CASCADE"), nullable=False)
    entity_type = Column(String(32), nullable=False)
    entity_id = Column(Uuid(as_uuid=True), nullable=False)


class DashboardFolderShare(Base, TimestampMixin):
    __tablename__ = "dashboard_folder_shares"
    __table_args__ = (UniqueConstraint("folder_id", "shared_with_user_id", name="uq_folder_share"),)

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    folder_id = Column(Uuid(as_uuid=True), ForeignKey("dashboard_folders.id", ondelete="CASCADE"), nullable=False)
    shared_with_user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    permission = Column(String(16), nullable=False, default="view")
