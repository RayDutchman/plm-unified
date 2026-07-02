"""用户组模型。"""
import uuid
from sqlalchemy import Column, String, Text, ForeignKey, Table, Uuid
from app.database import Base
from app.models.mixins import TimestampMixin


user_group_members = Table(
    "user_group_members",
    Base.metadata,
    Column("user_id", Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("group_id", Uuid(as_uuid=True), ForeignKey("user_groups.id", ondelete="CASCADE"), primary_key=True),
)


class UserGroup(Base, TimestampMixin):
    __tablename__ = "user_groups"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(64), unique=True, nullable=False)
    description = Column(Text, nullable=True)
