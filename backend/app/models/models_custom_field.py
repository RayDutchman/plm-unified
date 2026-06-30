"""自定义字段模型。"""
import uuid
from sqlalchemy import Column, String, Text, Boolean, Uuid, Integer, JSON, ForeignKey, Float
from app.database import Base
from app.models.mixins import TimestampMixin


class CustomFieldDefinition(Base, TimestampMixin):
    __tablename__ = "custom_field_definitions"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(128), nullable=False)
    field_key = Column(String(64), unique=True, nullable=False)
    field_type = Column(String(32), nullable=False)
    options = Column(JSON, nullable=True)
    is_required = Column(Boolean, nullable=False, default=False)
    applies_to = Column(JSON, nullable=True)
    sort_order = Column(Integer, nullable=False, default=0)


class CustomFieldValue(Base, TimestampMixin):
    __tablename__ = "custom_field_values"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    field_id = Column(Uuid(as_uuid=True), ForeignKey("custom_field_definitions.id", ondelete="CASCADE"), nullable=False)
    entity_type = Column(String(32), nullable=False)
    entity_id = Column(String(64), nullable=False)
    value_text = Column(Text, nullable=True)
    value_number = Column(Float, nullable=True)
    value_json = Column(JSON, nullable=True)
