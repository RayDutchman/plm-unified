import uuid
from sqlalchemy import Column, String, Integer, DateTime, Numeric, Text, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from app.database import Base


class CustomFieldDefinition(Base):
    __tablename__ = "custom_field_definitions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(128), nullable=False)
    field_key = Column(String(64), unique=True, nullable=False)
    field_type = Column(String(32), nullable=False)
    options = Column(JSONB, default=[])
    is_required = Column(Integer, default=0)
    applies_to = Column(JSONB, nullable=False, default=[])
    sort_order = Column(Integer, default=0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class CustomFieldValue(Base):
    __tablename__ = "custom_field_values"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    field_id = Column(UUID(as_uuid=True), ForeignKey('custom_field_definitions.id', ondelete='CASCADE'), nullable=False)
    entity_type = Column(String(32), nullable=False)
    entity_id = Column(UUID(as_uuid=True), nullable=False)
    value_text = Column(Text, nullable=True)
    value_number = Column(Numeric(12, 4), nullable=True)
    value_json = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
