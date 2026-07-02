"""
ECO (Engineering Change Order) - CRUD Operations
==================================================
变更管理 - ECO 模块数据库操作
"""
import uuid
from sqlalchemy.orm import Session
from sqlalchemy import func as sqlfunc
from fastapi import HTTPException
from datetime import datetime, timezone

from app.models.models_eco import ECO, ECOExecutionItem, ECOReviewRecord, ECOStatusLog
from app.models import User, PartMaster, PartRevision
from app.schemas.eco import ECOCreate, ECOUpdate, ECOListParams, ECOExecutionItemCreate, ECOExecutionItemEdit

_ALLOWED_TRANSITIONS = {
    "draft":     {"reviewing", "approved"},
    "reviewing": {"approved", "rejected", "draft"},
    "approved":  {"executing"},
    "executing": {"completed"},
    "completed": set(),
    "rejected":  {"draft"},
}


def generate_eco_number(db: Session) -> str:
    current_year = datetime.now(timezone.utc).year
    prefix = f"ECO-{current_year}-"
    max_number = db.query(
        sqlfunc.max(ECO.eco_number)
    ).filter(
        ECO.eco_number.like(f"{prefix}%")
    ).scalar()
    if max_number:
        seq_str = max_number[len(prefix):]
        try:
            seq = int(seq_str) + 1
        except ValueError:
            seq = 1
    else:
        seq = 1
    return f"{prefix}{seq:05d}"


def _build_reviewers_json(db: Session, reviewer_items: list) -> list:
    result = []
    for item in reviewer_items:
        uid = item.get("user_id", "") if isinstance(item, dict) else getattr(item, "user_id", "")
        seq = item.get("seq", 0) if isinstance(item, dict) else getattr(item, "seq", 0)
        if not uid or not str(uid).strip():
            continue
        try:
            user_id = uuid.UUID(uid) if isinstance(uid, str) else uid
        except (ValueError, AttributeError):
            continue
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            result.append({
                "seq": seq,
                "user_id": str(user_id),
                "user_name": user.real_name,
                "role": user.role,
            })
    return result


def _lookup_entity(db: Session, entity_type: str, entity_id: uuid.UUID):
    code, name, version = "", "", ""
    if entity_type in ("part", "component", "assembly"):
        entity = db.query(PartMaster).filter(PartMaster.id == entity_id).first()
        if entity:
            code = entity.number or ""
            name = entity.name or ""
    return code, name, version


def create_eco(db: Session, data: ECOCreate, creator_id: uuid.UUID) -> ECO:
    eco_number = generate_eco_number(db)
    reviewers_json = _build_reviewers_json(db, data.reviewers) if data.reviewers else []
    document_links_json = [dl.model_dump() if hasattr(dl, "model_dump") else dl for dl in (data.document_links or [])]
    ecr_id_val = uuid.UUID(data.ecr_id) if data.ecr_id else None

    db_eco = ECO(
        eco_number=eco_number,
        title=data.title,
        description=data.description,
        reason=data.reason,
        priority=data.priority,
        category=data.category,
        status="draft",
        reviewers=reviewers_json,
        review_mode=data.review_mode,
        creator_id=creator_id,
        document_links=document_links_json,
        ecr_id=ecr_id_val,
        release_items=data.release_items or [],
    )
    db.add(db_eco)
    db.commit()
    db.refresh(db_eco)

    if ecr_id_val:
        from app.models.models_ecr import ECR as ECRModel
        ecr = db.query(ECRModel).filter(ECRModel.id == ecr_id_val).first()
        if ecr:
            ecr.eco_id = db_eco.id
            db.commit()

    if data.execution_items:
        for idx, item in enumerate(data.execution_items):
            ei_data = item if isinstance(item, dict) else item.model_dump() if hasattr(item, "model_dump") else {}
            ei = ECOExecutionItem(
                eco_id=db_eco.id,
                source=ei_data.get("source", "manual"),
                entity_type=ei_data.get("entity_type", "part"),
                entity_name=ei_data.get("entity_name", ""),
                action=ei_data.get("action", "upgrade"),
                entity_id=uuid.UUID(ei_data["entity_id"]) if ei_data.get("entity_id") else None,
                entity_code=ei_data.get("entity_code"),
                entity_version=ei_data.get("entity_version"),
                parent_entity_id=uuid.UUID(ei_data["parent_entity_id"]) if ei_data.get("parent_entity_id") else None,
                detail=ei_data.get("detail", {}),
                sort_order=idx,
            )
            db.add(ei)
        db.commit()

    return db_eco


def get_ecos(db: Session, params: ECOListParams, current_user=None,
             include_deleted: bool = False, updated_since: float | None = None):
    from sqlalchemy import or_, cast, String
    q = db.query(ECO)

    if current_user and current_user.role != "admin":
        uid = str(current_user.id)
        q = q.filter(
            or_(
                ECO.creator_id == current_user.id,
                ECO.reviewers.cast(String).contains(f'"user_id": "{uid}"'),
                ECO.cc_users.cast(String).contains(f'"user_id": "{uid}"')
            )
        )

    if params.status:
        q = q.filter(ECO.status == params.status)
    if params.priority:
        q = q.filter(ECO.priority == params.priority)
    if params.search:
        pattern = f"%{params.search}%"
        q = q.filter(
            (ECO.title.ilike(pattern)) | (ECO.eco_number.ilike(pattern))
        )

    if not include_deleted:
        q = q.filter(ECO.deleted_at.is_(None))
    if updated_since:
        since_dt = datetime.fromtimestamp(updated_since, tz=timezone.utc)
        q = q.filter(
            (ECO.updated_at >= since_dt) |
            (ECO.deleted_at >= since_dt)
        )

    total = q.count()
    ecos = q.order_by(ECO.created_at.desc()).offset(
        (params.page - 1) * params.page_size
    ).limit(params.page_size).all()

    items = []
    for eco in ecos:
        creator = db.query(User).filter(User.id == eco.creator_id).first()
        creator_name = creator.real_name if creator else ""

        reviewers_count = len(eco.reviewers) if eco.reviewers else 0
        approved_count = db.query(ECOReviewRecord).filter(
            ECOReviewRecord.eco_id == eco.id,
            ECOReviewRecord.decision == "approved"
        ).count()
        execution_count = db.query(ECOExecutionItem).filter(
            ECOExecutionItem.eco_id == eco.id
        ).count()
        execution_completed_count = db.query(ECOExecutionItem).filter(
            ECOExecutionItem.eco_id == eco.id,
            ECOExecutionItem.status == "completed"
        ).count()

        ecr_number = None
        if eco.ecr_id:
            from app.models.models_ecr import ECR as ECRModel
            ecr = db.query(ECRModel).filter(ECRModel.id == eco.ecr_id).first()
            ecr_number = ecr.ecr_number if ecr else None

        items.append({
            "id": eco.id,
            "eco_number": eco.eco_number,
            "title": eco.title,
            "status": eco.status,
            "priority": eco.priority,
            "category": eco.category,
            "creator_name": creator_name,
            "reviewers_count": reviewers_count,
            "approved_count": approved_count,
            "execution_count": execution_count,
            "execution_completed_count": execution_completed_count,
            "ecr_id": str(eco.ecr_id) if eco.ecr_id else None,
            "ecr_number": ecr_number,
            "created_at": eco.created_at,
            "updated_at": eco.updated_at,
            "deleted_at": eco.deleted_at,
        })

    return items, total


def get_eco(db: Session, eco_id: uuid.UUID) -> ECO:
    eco = db.query(ECO).filter(ECO.id == eco_id, ECO.deleted_at.is_(None)).first()
    if not eco:
        raise HTTPException(status_code=404, detail="ECO 不存在")
    return eco


def update_eco(db: Session, eco: ECO, data: ECOUpdate):
    if eco.status != "draft":
        raise HTTPException(status_code=400, detail="仅草稿状态的 ECO 可以编辑")

    update_data = data.model_dump(exclude_unset=True)

    if "reviewers" in update_data and update_data["reviewers"] is not None:
        update_data["reviewers"] = _build_reviewers_json(db, update_data["reviewers"])

    if "ecr_id" in update_data and update_data["ecr_id"] is not None:
        update_data["ecr_id"] = uuid.UUID(update_data["ecr_id"]) if update_data["ecr_id"] else None

    if "document_links" in update_data and update_data["document_links"] is not None:
        update_data["document_links"] = [
            dl.model_dump() if hasattr(dl, "model_dump") else dl
            for dl in update_data["document_links"]
        ]

    for field, value in update_data.items():
        setattr(eco, field, value)

    eco.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(eco)
    return eco


def delete_eco(db: Session, eco_id: uuid.UUID) -> bool:
    eco = db.query(ECO).filter(ECO.id == eco_id, ECO.deleted_at.is_(None)).first()
    if not eco:
        return False
    eco.deleted_at = sqlfunc.now()
    db.commit()
    return True


def change_eco_status(db: Session, eco_id: uuid.UUID, to_status: str,
                      operator_id: uuid.UUID, comment: str = "", skip_log: bool = False) -> ECO:
    eco = get_eco(db, eco_id)
    from_status = eco.status

    allowed = _ALLOWED_TRANSITIONS.get(from_status, set())
    if to_status not in allowed:
        raise HTTPException(status_code=400, detail=f"不允许从 {from_status} 变更为 {to_status}")

    operator = db.query(User).filter(User.id == operator_id).first()
    operator_name = operator.real_name if operator else ""

    if not skip_log:
        log = ECOStatusLog(
            eco_id=eco_id,
            from_status=from_status,
            to_status=to_status,
            operator_id=operator_id,
            operator_name=operator_name,
            comment=comment,
        )
        db.add(log)

    eco.status = to_status
    now = datetime.now(timezone.utc)
    if to_status in ("approved", "rejected"):
        eco.reviewed_at = now
    elif to_status == "completed":
        eco.executed_at = now
    elif to_status == "closed":
        eco.closed_at = now
    eco.updated_at = now

    db.commit()
    db.refresh(eco)
    return eco


def add_eco_review_record(db: Session, eco_id: uuid.UUID, reviewer_id: uuid.UUID,
                          decision: str, comment: str = "") -> ECOReviewRecord:
    reviewer = db.query(User).filter(User.id == reviewer_id).first()
    if not reviewer:
        raise HTTPException(status_code=404, detail="审批人不存在")

    r = ECOReviewRecord(
        eco_id=eco_id,
        reviewer_id=reviewer_id,
        reviewer_name=reviewer.real_name,
        decision=decision,
        comment=comment,
    )
    db.add(r)
    db.commit()
    db.refresh(r)
    return r


def check_all_approved(db: Session, eco_id: uuid.UUID) -> bool:
    eco = db.query(ECO).filter(ECO.id == eco_id).first()
    if not eco:
        return False

    reviewers = eco.reviewers or []
    if not reviewers:
        return False

    rids = set()
    for r in reviewers:
        try:
            rids.add(uuid.UUID(r["user_id"]))
        except (ValueError, KeyError):
            pass

    if not rids:
        return False

    approved = db.query(ECOReviewRecord).filter(
        ECOReviewRecord.eco_id == eco_id,
        ECOReviewRecord.decision == "approved"
    ).all()
    aids = set(r.reviewer_id for r in approved)

    return len(aids & rids) > 0 if eco.review_mode == "any" else rids.issubset(aids)


def clear_review_records(db: Session, eco_id: uuid.UUID):
    db.query(ECOReviewRecord).filter(ECOReviewRecord.eco_id == eco_id).delete()
    db.commit()


def get_execution_items(db: Session, eco_id: uuid.UUID) -> list:
    return db.query(ECOExecutionItem).filter(
        ECOExecutionItem.eco_id == eco_id
    ).order_by(ECOExecutionItem.sort_order).all()


def get_execution_item(db: Session, item_id: uuid.UUID):
    return db.query(ECOExecutionItem).filter(
        ECOExecutionItem.id == item_id
    ).first()


def add_execution_item(db: Session, eco: ECO, data: ECOExecutionItemCreate) -> ECOExecutionItem:
    if eco.status != "draft":
        raise HTTPException(status_code=400, detail="仅草稿状态的 ECO 可以添加执行项")

    item = ECOExecutionItem(
        eco_id=eco.id,
        source=data.source,
        entity_type=data.entity_type,
        entity_name=data.entity_name or "",
        action=data.action,
        entity_id=uuid.UUID(data.entity_id) if data.entity_id else None,
        entity_code=data.entity_code,
        entity_version=data.entity_version,
        parent_entity_id=None,
        sort_order=data.sort_order,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def update_execution_item(db: Session, item: ECOExecutionItem, data: ECOExecutionItemEdit):
    updatable = {"entity_name", "entity_code", "action", "sort_order", "parent_entity_id"}
    update_data = data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        if field in updatable and value is not None:
            setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


def remove_execution_item(db: Session, eco_id: uuid.UUID, item_id: uuid.UUID):
    item = db.query(ECOExecutionItem).filter(
        ECOExecutionItem.id == item_id, ECOExecutionItem.eco_id == eco_id
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="执行项不存在")
    db.delete(item)
    db.commit()


def add_cc_users(db: Session, eco: ECO, user_ids: list):
    current = list(eco.cc_users or [])
    existing_ids = {u.get("user_id") for u in current}
    for uid in user_ids:
        if uid in existing_ids:
            continue
        user = db.query(User).filter(User.id == uuid.UUID(uid)).first()
        if user:
            current.append({"user_id": uid, "user_name": user.real_name})
    eco.cc_users = current
    db.commit()
    db.refresh(eco)
    return eco


def remove_cc_user(db: Session, eco: ECO, user_id: str):
    current = list(eco.cc_users or [])
    current = [u for u in current if u.get("user_id") != user_id]
    eco.cc_users = current
    db.commit()
    db.refresh(eco)
    return eco


def get_status_logs(db: Session, eco_id: uuid.UUID) -> list:
    return db.query(ECOStatusLog).filter(
        ECOStatusLog.eco_id == eco_id
    ).order_by(ECOStatusLog.created_at).all()


def _upgrade_entity(db: Session, entity_type: str, entity_id: uuid.UUID) -> tuple:
    master = db.query(PartMaster).filter(PartMaster.id == entity_id).first()
    if not master:
        raise HTTPException(status_code=404, detail=f"PartMaster {entity_id} 不存在")
    revisions = db.query(PartRevision).filter(
        PartRevision.part_master_id == entity_id
    ).order_by(PartRevision.created_at.desc()).all()
    latest_version = revisions[0].version if revisions else "A"
    next_v = _next_version_str(latest_version)
    new_rev = PartRevision(
        part_master_id=entity_id,
        version=next_v,
        status="WIP",
    )
    db.add(new_rev)
    db.flush()
    return new_rev.id, next_v


def _release_entity(db: Session, entity_type: str, entity_id: uuid.UUID):
    revision = db.query(PartRevision).filter(PartRevision.id == entity_id).first()
    if not revision:
        raise HTTPException(status_code=404, detail=f"PartRevision {entity_id} 不存在")
    revision.status = "RELEASED"
    revision.released_at = datetime.now(timezone.utc)


def _freeze_entity(db: Session, entity_type: str, entity_id: uuid.UUID):
    revision = db.query(PartRevision).filter(PartRevision.id == entity_id).first()
    if not revision:
        raise HTTPException(status_code=404, detail=f"PartRevision {entity_id} 不存在")
    revision.status = "OBSOLETE"
    revision.obsoleted_at = datetime.now(timezone.utc)


def _revert_entity(db: Session, entity_type: str, entity_id: uuid.UUID):
    revision = db.query(PartRevision).filter(PartRevision.id == entity_id).first()
    if not revision:
        raise HTTPException(status_code=404, detail=f"PartRevision {entity_id} 不存在")
    revision.status = "WIP"


VERSION_CHARS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def _next_version_str(current: str) -> str:
    if not current:
        return "A"
    chars = list(current.upper())
    i = len(chars) - 1
    while i >= 0:
        idx = VERSION_CHARS.index(chars[i]) if chars[i] in VERSION_CHARS else -1
        if idx >= 0 and idx < len(VERSION_CHARS) - 1:
            chars[i] = VERSION_CHARS[idx + 1]
            return "".join(chars)
        elif idx == len(VERSION_CHARS) - 1:
            chars[i] = "A"
            i -= 1
        else:
            break
    return "A" + "".join(chars)


def execute_item(db: Session, item: ECOExecutionItem) -> ECOExecutionItem:
    if item.status not in ("pending", "failed"):
        raise HTTPException(status_code=400, detail=f"执行项状态为 {item.status}，不可执行")

    item.status = "in_progress"
    db.commit()

    try:
        if item.action == "upgrade":
            if not item.entity_id:
                raise HTTPException(status_code=400, detail="执行项缺少 entity_id")
            new_id, new_version = _upgrade_entity(db, item.entity_type, item.entity_id)
            item.new_entity_id = new_id
            item.new_version = new_version
            item.detail = {**(item.detail or {}), "new_entity_id": str(new_id), "new_version": new_version}
        elif item.action == "release":
            target_id = item.new_entity_id or item.entity_id
            if not target_id:
                raise HTTPException(status_code=400, detail="执行项缺少实体 ID")
            _release_entity(db, item.entity_type, target_id)
        elif item.action == "freeze":
            target_id = item.new_entity_id or item.entity_id
            if not target_id:
                raise HTTPException(status_code=400, detail="执行项缺少实体 ID")
            _freeze_entity(db, item.entity_type, target_id)
        elif item.action == "revert":
            target_id = item.new_entity_id or item.entity_id
            if not target_id:
                raise HTTPException(status_code=400, detail="执行项缺少实体 ID")
            _revert_entity(db, item.entity_type, target_id)
        else:
            pass

        item.status = "completed"
        item.executed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(item)

    except Exception as e:
        item.status = "failed"
        item.error_message = str(e)
        db.commit()
        db.refresh(item)

    return item


def execute_all(db: Session, eco: ECO) -> list:
    items = db.query(ECOExecutionItem).filter(
        ECOExecutionItem.eco_id == eco.id
    ).order_by(ECOExecutionItem.sort_order).all()

    results = []
    for item in items:
        if item.status in ("completed", "skipped"):
            results.append({"id": str(item.id), "status": item.status})
            continue
        try:
            executed = execute_item(db, item)
            results.append({"id": str(executed.id), "status": executed.status})
        except Exception as e:
            results.append({"id": str(item.id), "status": "failed", "error": str(e)})

    return results
