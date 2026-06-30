from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
import uuid

from app.database import get_db
from app.models import User
from app import crud_custom_field
from app import schemas_custom_field as schemas
from app.crud import create_log
from app.core.permissions import require_permission

router = APIRouter(prefix="/custom-fields", tags=["自定义字段管理"])


def _def_response(field_def):
    return {
        "id": field_def.id,
        "name": field_def.name,
        "field_key": field_def.field_key,
        "field_type": field_def.field_type,
        "options": field_def.options or [],
        "is_required": bool(field_def.is_required),
        "applies_to": field_def.applies_to,
        "sort_order": field_def.sort_order,
        "created_at": field_def.created_at,
        "updated_at": field_def.updated_at,
    }


def _value_response(val, field_def=None):
    value = None
    if field_def:
        if field_def.field_type == 'text' or field_def.field_type == 'select':
            value = val.value_text
        elif field_def.field_type == 'number':
            value = float(val.value_number) if val.value_number is not None else None
        elif field_def.field_type == 'multiselect':
            value = val.value_json
    else:
        value = val.value_text or (float(val.value_number) if val.value_number is not None else None) or val.value_json

    return {
        "field_id": val.field_id,
        "field_key": field_def.field_key if field_def else None,
        "field_name": field_def.name if field_def else None,
        "field_type": field_def.field_type if field_def else None,
        "value": value,
    }


@router.get("/definitions/", response_model=list[schemas.CustomFieldDefinitionResponse])
async def list_definitions(
    applies_to: str = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("custom_field.def:read"))
):
    definitions = crud_custom_field.get_custom_field_definitions(db, applies_to=applies_to)
    return [_def_response(d) for d in definitions]


@router.post("/definitions/", response_model=schemas.CustomFieldDefinitionResponse)
async def create_definition(
    field_def: schemas.CustomFieldDefinitionCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("custom_field.def:write"))
):
    existing = crud_custom_field.get_custom_field_definition_by_key(db, field_def.field_key)
    if existing:
        raise HTTPException(status_code=400, detail=f"字段标识 '{field_def.field_key}' 已存在")
    db_field = crud_custom_field.create_custom_field_definition(db, field_def)
    ip = request.client.host if request.client else None
    create_log(db, current_user.id, current_user.username, "创建自定义字段", "custom_field", str(db_field.id), f"名称:{field_def.name} 标识:{field_def.field_key}", ip)
    return _def_response(db_field)


@router.put("/definitions/{field_id}", response_model=schemas.CustomFieldDefinitionResponse)
async def update_definition(
    field_id: uuid.UUID,
    field_update: schemas.CustomFieldDefinitionUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("custom_field.def:write"))
):
    db_field = crud_custom_field.update_custom_field_definition(db, field_id, field_update)
    if not db_field:
        raise HTTPException(status_code=404, detail="字段定义不存在")
    ip = request.client.host if request.client else None
    create_log(db, current_user.id, current_user.username, "更新自定义字段", "custom_field", str(field_id), None, ip)
    return _def_response(db_field)


@router.delete("/definitions/{field_id}")
async def delete_definition(
    field_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("custom_field.def:write"))
):
    db_field = crud_custom_field.get_custom_field_definition(db, field_id)
    if not db_field:
        raise HTTPException(status_code=404, detail="字段定义不存在")
    ip = request.client.host if request.client else None
    create_log(db, current_user.id, current_user.username, "删除自定义字段", "custom_field", str(field_id), f"名称:{db_field.name}", ip)
    crud_custom_field.delete_custom_field_definition(db, field_id)
    return {"message": "字段定义已删除"}


@router.put("/definitions/reorder")
async def reorder_definitions(
    reorder: schemas.ReorderRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("custom_field.def:sort"))
):
    crud_custom_field.reorder_custom_field_definitions(db, reorder.items)
    return {"message": "排序已更新"}


@router.get("/values/batch")
async def get_values_batch(
    type: str,
    ids: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("custom_field.value:read"))
):
    if type not in ('part', 'component', 'assembly', 'document'):
        raise HTTPException(status_code=400, detail="type 必须为 part、component/assembly 或 document")

    entity_ids = [id.strip() for id in ids.split(',') if id.strip()]
    if not entity_ids:
        return {}

    result = crud_custom_field.get_custom_field_values_batch(db, type, entity_ids)
    return result


@router.get("/values/{entity_type}/{entity_id}", response_model=list[schemas.CustomFieldValueResponse])
async def get_values(
    entity_type: str,
    entity_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("custom_field.value:read"))
):
    if entity_type not in ('part', 'component', 'document'):
        raise HTTPException(status_code=400, detail="entity_type 必须为 part、component 或 document")
    results = crud_custom_field.get_custom_field_values(db, entity_type, entity_id)
    return [_value_response(val, field_def) for val, field_def in results]


@router.put("/values/{entity_type}/{entity_id}")
async def set_values(
    entity_type: str,
    entity_id: str,
    batch: schemas.CustomFieldValuesBatch,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("custom_field.value:write"))
):
    if entity_type not in ('part', 'component', 'document'):
        raise HTTPException(status_code=400, detail="entity_type 必须为 part、component 或 document")
    crud_custom_field.assert_entity_editable(db, entity_type, entity_id, current_user.role)
    crud_custom_field.set_custom_field_values(db, entity_type, entity_id, batch.values)
    ip = request.client.host if request.client else None
    create_log(db, current_user.id, current_user.username, "更新自定义字段值", entity_type, str(entity_id), f"{len(batch.values)}个字段", ip)
    return {"message": "字段值已更新"}


@router.post("/reset-data")
async def reset_business_data(
    data: dict,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("custom_field:reset_data"))
):
    password = data.get("password", "")
    if not password:
        raise HTTPException(status_code=400, detail="请输入管理员密码")

    from app.core.security import verify_password
    if not verify_password(password, current_user.password_hash):
        raise HTTPException(status_code=403, detail="密码错误")

    crud_custom_field._reset_business_data(db)
    return {"message": "业务数据已重置"}
