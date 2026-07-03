import uuid
from datetime import datetime

from sqlalchemy.orm import Session, aliased

from app.models.models_custom_field import CustomFieldDefinition, CustomFieldValue
from app.core.security import verify_password


def get_custom_field_definitions(db: Session, applies_to=None):
    q = db.query(CustomFieldDefinition)
    if applies_to and applies_to != 'all':
        types = [t.strip() for t in applies_to.split(',')]
        if types:
            q = q.filter(CustomFieldDefinition.applies_to.overlap(types))
    return q.order_by(CustomFieldDefinition.sort_order, CustomFieldDefinition.created_at).all()


def get_custom_field_definition(db: Session, field_id):
    return db.query(CustomFieldDefinition).filter(CustomFieldDefinition.id == field_id).first()


def get_custom_field_definition_by_key(db: Session, field_key):
    return db.query(CustomFieldDefinition).filter(CustomFieldDefinition.field_key == field_key).first()


def create_custom_field_definition(db: Session, field_def):
    applies_to_val = field_def.applies_to
    if isinstance(applies_to_val, str):
        applies_to_val = [applies_to_val]
    kwargs = dict(
        name=field_def.name,
        field_key=field_def.field_key,
        field_type=field_def.field_type,
        options=field_def.options or [],
        is_required=1 if field_def.is_required else 0,
        applies_to=applies_to_val,
        sort_order=field_def.sort_order,
    )
    if field_def.id:
        kwargs['id'] = field_def.id
    db_field = CustomFieldDefinition(**kwargs)
    db.add(db_field)
    db.commit()
    db.refresh(db_field)
    return db_field


def update_custom_field_definition(db: Session, field_id, field_update):
    db_field = get_custom_field_definition(db, field_id)
    if not db_field:
        return None
    update_data = field_update.model_dump(exclude_unset=True)
    if 'is_required' in update_data:
        update_data['is_required'] = 1 if update_data['is_required'] else 0
    if 'applies_to' in update_data:
        if isinstance(update_data['applies_to'], str):
            update_data['applies_to'] = [update_data['applies_to']]
    for field, value in update_data.items():
        setattr(db_field, field, value)
    db_field.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(db_field)
    return db_field


def delete_custom_field_definition(db: Session, field_id):
    db_field = get_custom_field_definition(db, field_id)
    if db_field:
        db.delete(db_field)
        db.commit()
    return db_field


def reorder_custom_field_definitions(db: Session, items):
    for item in items:
        db_field = db.query(CustomFieldDefinition).filter(CustomFieldDefinition.id == item.id).first()
        if db_field:
            db_field.sort_order = item.sort_order
    db.commit()
    return True


def get_custom_field_values(db: Session, entity_type, entity_id):
    CFD = CustomFieldDefinition
    CFV = CustomFieldValue
    results = db.query(CFV, CFD).join(CFD, CFV.field_id == CFD.id).filter(
        CFV.entity_type == entity_type,
        CFV.entity_id == entity_id,
    ).all()
    return results


def get_custom_field_values_batch(db: Session, entity_type, entity_ids):
    from collections import defaultdict
    CFV = CustomFieldValue
    CFD = CustomFieldDefinition

    all_defs = db.query(CFD).filter(
        CFD.applies_to.contains(entity_type)
    ).all()

    results = db.query(CFV, CFD).join(CFD, CFV.field_id == CFD.id).filter(
        CFV.entity_type == entity_type,
        CFV.entity_id.in_(entity_ids),
    ).all()

    output = defaultdict(dict)
    for val, field_def in results:
        entity_id_str = str(val.entity_id)
        value = None
        if field_def.field_type in ('text', 'select'):
            value = val.value_text
        elif field_def.field_type == 'number':
            value = float(val.value_number) if val.value_number is not None else None
        elif field_def.field_type == 'multiselect':
            value = val.value_json
        else:
            value = val.value_text or (float(val.value_number) if val.value_number is not None else None) or val.value_json
        output[entity_id_str][field_def.field_key] = value

    return dict(output)


def _value_to_display(field_def, value_text, value_number, value_json):
    """把数据库中存储的自定义字段值转换为可读字符串。"""
    if field_def.field_type == 'number':
        return str(value_number) if value_number is not None else None
    if field_def.field_type == 'multiselect':
        return ', '.join(value_json) if value_json else None
    return value_text


def set_custom_field_values(db: Session, entity_type, entity_id, values):
    """批量设置自定义字段值，返回变更详情列表 [(字段名称, 旧值, 新值), ...]。"""
    changed = []
    for item in values:
        field_def = get_custom_field_definition(db, item.field_id)
        if not field_def:
            continue
        existing = db.query(CustomFieldValue).filter(
            CustomFieldValue.field_id == item.field_id,
            CustomFieldValue.entity_type == entity_type,
            CustomFieldValue.entity_id == entity_id,
        ).first()

        value_text = None
        value_number = None
        value_json = None
        if field_def.field_type == 'text':
            value_text = str(item.value) if item.value is not None else None
        elif field_def.field_type == 'number':
            try:
                value_number = float(item.value) if item.value is not None else None
            except (ValueError, TypeError):
                value_number = None
        elif field_def.field_type == 'select':
            value_text = str(item.value) if item.value is not None else None
        elif field_def.field_type == 'multiselect':
            value_json = item.value if isinstance(item.value, list) else None

        old_display = _value_to_display(field_def, existing.value_text, existing.value_number, existing.value_json) if existing else None
        new_display = _value_to_display(field_def, value_text, value_number, value_json)

        if existing:
            # 只有当值真正变化时才更新，并记录变更
            if (existing.value_text != value_text or
                existing.value_number != value_number or
                existing.value_json != value_json):
                existing.value_text = value_text
                existing.value_number = value_number
                existing.value_json = value_json
                existing.updated_at = datetime.utcnow()
                changed.append((field_def.name, old_display, new_display))
        else:
            # 原无值且新值也为空，不创建记录
            if value_text is None and value_number is None and value_json is None:
                continue
            new_val = CustomFieldValue(
                field_id=item.field_id,
                entity_type=entity_type,
                entity_id=entity_id,
                value_text=value_text,
                value_number=value_number,
                value_json=value_json,
            )
            if item.id:
                new_val.id = item.id
            db.add(new_val)
            changed.append((field_def.name, old_display, new_display))
    db.commit()
    return changed


def assert_entity_editable(db: Session, entity_type: str, entity_id, user_role: str):
    if user_role == "admin":
        return
    from app.models.part import PartMaster, PartRevision
    from fastapi import HTTPException
    revision = db.query(PartRevision).filter(PartRevision.id == entity_id).first()
    if revision and revision.status in ("OBSOLETE", "RELEASED"):
        label = "已冻结" if revision.status == "OBSOLETE" else "已发布"
        raise HTTPException(status_code=403, detail=f"该零部件{label}，审批/发布期间不可修改（仅管理员可修改）")


def _reset_business_data(db: Session):
    db.query(CustomFieldValue).delete()
    db.query(CustomFieldDefinition).delete()
    db.commit()


def _copy_custom_field_values(db: Session, entity_type: str, old_entity_id, new_entity_id):
    old_values = db.query(CustomFieldValue).filter(
        CustomFieldValue.entity_type == entity_type,
        CustomFieldValue.entity_id == old_entity_id,
    ).all()
    for ov in old_values:
        new_val = CustomFieldValue(
            field_id=ov.field_id,
            entity_type=entity_type,
            entity_id=new_entity_id,
            value_text=ov.value_text,
            value_number=ov.value_number,
            value_json=ov.value_json,
        )
        db.add(new_val)
    db.commit()
