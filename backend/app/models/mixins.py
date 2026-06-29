"""模型公共 Mixin：时间戳与软删除。"""
from sqlalchemy import Column, DateTime, func


class TimestampMixin:
    # 自动维护：插入设 now，更新刷新 updated_at
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class SoftDeleteMixin:
    # 软删除标记：非空表示已删除
    deleted_at = Column(DateTime(timezone=True), nullable=True)
