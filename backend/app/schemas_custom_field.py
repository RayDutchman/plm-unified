from pydantic import BaseModel, Field, BeforeValidator
from typing import Optional, List, Any, Annotated
from datetime import datetime
import uuid


def _normalize_applies_to(v):
    if isinstance(v, str):
        return [v]
    if isinstance(v, list):
        return v
    return ['part']


AppliesToList = Annotated[List[str], BeforeValidator(_normalize_applies_to)]


class CustomFieldDefinitionBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    field_key: str = Field(..., min_length=1, max_length=64, pattern=r'^[a-zA-Z][a-zA-Z0-9_]*$')
    field_type: str = Field(..., pattern=r'^(text|number|select|multiselect)$')
    options: Optional[List[str]] = None
    is_required: bool = False
    applies_to: AppliesToList = Field(default=['part'])
    sort_order: int = 0


class CustomFieldDefinitionCreate(CustomFieldDefinitionBase):
    id: Optional[uuid.UUID] = None


class CustomFieldDefinitionUpdate(BaseModel):
    name: Optional[str] = None
    field_type: Optional[str] = None
    options: Optional[List[str]] = None
    is_required: Optional[bool] = None
    applies_to: Optional[AppliesToList] = None
    sort_order: Optional[int] = None


class CustomFieldDefinitionResponse(CustomFieldDefinitionBase):
    id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    model_config = {"from_attributes": True}


class CustomFieldValueItem(BaseModel):
    id: Optional[uuid.UUID] = None
    field_id: uuid.UUID
    value: Optional[Any] = None


class CustomFieldValuesBatch(BaseModel):
    values: List[CustomFieldValueItem]


class CustomFieldValueResponse(BaseModel):
    field_id: uuid.UUID
    field_key: Optional[str] = None
    field_name: Optional[str] = None
    field_type: Optional[str] = None
    value: Optional[Any] = None
    model_config = {"from_attributes": True}


class ReorderItem(BaseModel):
    id: uuid.UUID
    sort_order: int


class ReorderRequest(BaseModel):
    items: List[ReorderItem]
