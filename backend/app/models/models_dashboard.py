"""用户看板 - SQLAlchemy Models
==============================
  - user_dashboards: 用户看板主表（每用户一个）
  - dashboard_folders: 看板文件夹（树形结构）
  - dashboard_items: 文件夹内容关联表
  - dashboard_folder_shares: 文件夹共享表
"""

import uuid
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.database import Base


class UserDashboard(Base):
    __tablename__ = "user_dashboards"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), unique=True, nullable=False)
    name = Column(String(128), default="我的看板")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    folders = relationship("DashboardFolder", back_populates="dashboard", cascade="all, delete-orphan")


class DashboardFolder(Base):
    __tablename__ = "dashboard_folders"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    dashboard_id = Column(UUID(as_uuid=True), ForeignKey('user_dashboards.id', ondelete='CASCADE'), nullable=False)
    parent_id = Column(UUID(as_uuid=True), ForeignKey('dashboard_folders.id', ondelete='CASCADE'), nullable=True)
    name = Column(String(128), nullable=False)
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    dashboard = relationship("UserDashboard", back_populates="folders")
    children = relationship("DashboardFolder", backref="parent", remote_side="DashboardFolder.id", cascade="save-update, merge")
    items = relationship("DashboardItem", back_populates="folder", cascade="all, delete-orphan")
    shares = relationship("DashboardFolderShare", back_populates="folder", cascade="all, delete-orphan")


class DashboardItem(Base):
    __tablename__ = "dashboard_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    folder_id = Column(UUID(as_uuid=True), ForeignKey('dashboard_folders.id', ondelete='CASCADE'), nullable=False)
    entity_type = Column(String(16), nullable=False)
    entity_id = Column(UUID(as_uuid=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    folder = relationship("DashboardFolder", back_populates="items")


class DashboardFolderShare(Base):
    __tablename__ = "dashboard_folder_shares"
    __table_args__ = (UniqueConstraint('folder_id', 'shared_with_user_id', name='uix_folder_share_user'),)

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    folder_id = Column(UUID(as_uuid=True), ForeignKey('dashboard_folders.id', ondelete='CASCADE'), nullable=False)
    shared_with_user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False)
    permission = Column(String(16), nullable=False, default="view")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    folder = relationship("DashboardFolder", back_populates="shares")
