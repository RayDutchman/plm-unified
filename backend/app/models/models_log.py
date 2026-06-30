import uuid
from sqlalchemy import Column, String, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from app.database import Base


class OperationLog(Base):
    __tablename__ = "operation_logs"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True))
    username = Column(String(64))
    action = Column(String(64), nullable=False)
    target_type = Column(String(32))
    target_id = Column(String(64))
    detail = Column(Text)
    ip_address = Column(String(64))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
