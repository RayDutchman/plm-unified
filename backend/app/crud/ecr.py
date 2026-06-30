"""
ECR (Engineering Change Request) - CRUD Operations
==================================================
变更管理 - ECR 模块数据库操作
"""
import uuid
from sqlalchemy.orm import Session
from sqlalchemy import func as sqlfunc
from fastapi import HTTPException
from datetime import datetime, timezone

from app.models.models_ecr import ECR, ECRAffectedItem, ECRReviewRecord, ECRStatusLog
from app.models import User, Component, PartMaster
from app.schemas.ecr import ECRCreate, ECRUpdate, ECRListParams, ECRAffectedItemCreate

_ALLOWED_TRANSITIONS = {
    "draft":     {"reviewing", "closed"},
    "reviewing": {"approved", "rejected", "draft"},
    "approved":  {"closed"},
    "rejected":  {"closed"},
}


def generate_ecr_number(db: Session) -> str:
    current_year = datetime.now(timezone.utc).year
    prefix = f"ECR-{current_year}-"
    max_number = db.query(
        sqlfunc.max(ECR.ecr_number)
    ).filter(
        ECR.ecr_number.like(f"{prefix}%")
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
        uid = item.user_id if hasattr(item, "user_id") else item.get("user_id", "")
        seq = item.seq if hasattr(item, "seq") else item.get("seq", 0)
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
    if entity_type in ("part",):
        entity = db.query(PartMaster).filter(PartMaster.id == entity_id).first()
        if entity:
            code = entity.number or ""
            name = entity.name or ""
    elif entity_type in ("component", "assembly"):
        entity = db.query(Component).filter(Component.id == entity_id).first()
        if entity:
            code = entity.code or ""
            name = entity.name or ""
            version = entity.version or ""
    return code, name, version


def create_ecr(db: Session, data: ECRCreate, creator_id: uuid.UUID) -> ECR:
    ecr_number = generate_ecr_number(db)
    reviewers_json = _build_reviewers_json(db, data.reviewers) if data.reviewers else []
    document_links_json = [dl.model_dump() if hasattr(dl, "model_dump") else dl for dl in data.document_links]

    db_ecr = ECR(
        ecr_number=ecr_number,
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
    )
    db.add(db_ecr)
    db.commit()
    db.refresh(db_ecr)
    return db_ecr


def get_ecrs(
    db: Session, params: ECRListParams, current_user=None,
    include_deleted: bool = False, updated_since: float | None = None,
):
    from sqlalchemy import or_, cast, String
    q = db.query(ECR)

    if current_user and current_user.role != "admin":
        uid = str(current_user.id)
        q = q.filter(
            or_(
                ECR.creator_id == current_user.id,
                ECR.reviewers.cast(String).contains(f'"user_id": "{uid}"'),
                ECR.cc_users.cast(String).contains(f'"user_id": "{uid}"')
            )
        )

    if params.status:
        q = q.filter(ECR.status == params.status)
    if params.priority:
        q = q.filter(ECR.priority == params.priority)
    if params.search:
        pattern = f"%{params.search}%"
        q = q.filter(
            (ECR.title.ilike(pattern)) | (ECR.ecr_number.ilike(pattern))
        )

    if not include_deleted:
        q = q.filter(ECR.deleted_at.is_(None))
    if updated_since:
        since_dt = datetime.fromtimestamp(updated_since, tz=timezone.utc)
        q = q.filter(
            (ECR.updated_at >= since_dt) |
            (ECR.deleted_at >= since_dt)
        )

    total = q.count()
    ecrs = q.order_by(ECR.created_at.desc()).offset(
        (params.page - 1) * params.page_size
    ).limit(params.page_size).all()

    items = []
    for ecr in ecrs:
        creator = db.query(User).filter(User.id == ecr.creator_id).first()
        creator_name = creator.real_name if creator else ""

        reviewers_count = len(ecr.reviewers) if ecr.reviewers else 0
        approved_count = db.query(ECRReviewRecord).filter(
            ECRReviewRecord.ecr_id == ecr.id,
            ECRReviewRecord.decision == "approved"
        ).count()
        affected_count = db.query(ECRAffectedItem).filter(
            ECRAffectedItem.ecr_id == ecr.id
        ).count()

        items.append({
            "id": ecr.id,
            "ecr_number": ecr.ecr_number,
            "title": ecr.title,
            "status": ecr.status,
            "priority": ecr.priority,
            "category": ecr.category,
            "creator_id": str(ecr.creator_id),
            "creator_name": creator_name,
            "reviewers_count": reviewers_count,
            "approved_count": approved_count,
            "affected_count": affected_count,
            "created_at": ecr.created_at,
            "updated_at": ecr.updated_at,
            "deleted_at": ecr.deleted_at,
        })

    return items, total


def get_ecr(db: Session, ecr_id: uuid.UUID) -> ECR:
    ecr = db.query(ECR).filter(ECR.id == ecr_id, ECR.deleted_at.is_(None)).first()
    if not ecr:
        raise HTTPException(status_code=404, detail="ECR 不存在")
    return ecr


def update_ecr(db: Session, ecr_id: uuid.UUID, data: ECRUpdate) -> ECR:
    ecr = get_ecr(db, ecr_id)
    if ecr.status != "draft":
        raise HTTPException(status_code=400, detail="仅草稿状态的 ECR 可以编辑")

    update_data = data.model_dump(exclude_unset=True)

    if "reviewers" in update_data and update_data["reviewers"] is not None:
        update_data["reviewers"] = _build_reviewers_json(db, update_data["reviewers"])

    if "document_links" in update_data and update_data["document_links"] is not None:
        update_data["document_links"] = [
            dl.model_dump() if hasattr(dl, "model_dump") else dl
            for dl in update_data["document_links"]
        ]

    for field, value in update_data.items():
        setattr(ecr, field, value)
    ecr.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(ecr)
    return ecr


def delete_ecr(db: Session, ecr_id: uuid.UUID) -> bool:
    ecr = db.query(ECR).filter(ECR.id == ecr_id, ECR.deleted_at.is_(None)).first()
    if not ecr:
        return False
    ecr.deleted_at = sqlfunc.now()
    db.commit()
    return True


def change_ecr_status(
    db: Session,
    ecr_id: uuid.UUID,
    to_status: str,
    operator_id: uuid.UUID,
    comment: str | None = None,
    skip_log: bool = False,
) -> ECR:
    ecr = get_ecr(db, ecr_id)
    from_status = ecr.status

    allowed = _ALLOWED_TRANSITIONS.get(from_status, set())
    if to_status not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"不允许从 {from_status} 变更为 {to_status}"
        )

    operator = db.query(User).filter(User.id == operator_id).first()
    operator_name = operator.real_name if operator else ""

    if not skip_log:
        log = ECRStatusLog(
            ecr_id=ecr_id,
            from_status=from_status,
            to_status=to_status,
            operator_id=operator_id,
            operator_name=operator_name,
            comment=comment,
        )
        db.add(log)

    ecr.status = to_status
    now = datetime.now(timezone.utc)
    if to_status in ("approved", "rejected"):
        ecr.reviewed_at = now
    elif to_status == "closed":
        ecr.closed_at = now
    ecr.updated_at = now

    db.commit()
    db.refresh(ecr)
    return ecr


def add_ecr_review_record(
    db: Session,
    ecr_id: uuid.UUID,
    reviewer_id: uuid.UUID,
    decision: str,
    comment: str | None = None
) -> ECRReviewRecord:
    reviewer = db.query(User).filter(User.id == reviewer_id).first()
    if not reviewer:
        raise HTTPException(status_code=404, detail="审批人不存在")

    record = ECRReviewRecord(
        ecr_id=ecr_id,
        reviewer_id=reviewer_id,
        reviewer_name=reviewer.real_name,
        decision=decision,
        comment=comment,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


def check_all_approved(db: Session, ecr_id: uuid.UUID) -> bool:
    ecr = db.query(ECR).filter(ECR.id == ecr_id).first()
    if not ecr:
        return False

    reviewers = ecr.reviewers or []
    if not reviewers:
        return False

    reviewer_ids = set()
    for r in reviewers:
        try:
            reviewer_ids.add(uuid.UUID(r["user_id"]))
        except (ValueError, KeyError):
            pass

    if not reviewer_ids:
        return False

    approved_records = db.query(ECRReviewRecord).filter(
        ECRReviewRecord.ecr_id == ecr_id,
        ECRReviewRecord.decision == "approved"
    ).all()

    approved_reviewer_ids = set(r.reviewer_id for r in approved_records)

    if ecr.review_mode == "any":
        return len(approved_reviewer_ids & reviewer_ids) > 0
    else:
        return reviewer_ids.issubset(approved_reviewer_ids)


def add_affected_item(
    db: Session,
    ecr_id: uuid.UUID,
    data: ECRAffectedItemCreate
) -> ECRAffectedItem:
    ecr = db.query(ECR).filter(ECR.id == ecr_id).first()
    if not ecr:
        raise HTTPException(status_code=404, detail="ECR 不存在")

    entity_id = uuid.UUID(data.entity_id) if isinstance(data.entity_id, str) else data.entity_id

    entity_code, entity_name, entity_version = _lookup_entity(db, data.entity_type, entity_id)

    item = ECRAffectedItem(
        ecr_id=ecr_id,
        entity_type=data.entity_type,
        entity_id=entity_id,
        entity_code=entity_code,
        entity_name=entity_name,
        entity_version=entity_version,
        change_description=data.change_description,
        change_type=data.change_type,
        bom_impact={},
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def get_affected_items(db: Session, ecr_id: uuid.UUID) -> list:
    return db.query(ECRAffectedItem).filter(
        ECRAffectedItem.ecr_id == ecr_id
    ).order_by(ECRAffectedItem.created_at).all()


def delete_affected_item(db: Session, item_id: uuid.UUID):
    item = db.query(ECRAffectedItem).filter(ECRAffectedItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="受影响对象不存在")
    db.delete(item)
    db.commit()


def _get_upward_trace(db: Session, entity_type: str, entity_id: uuid.UUID) -> list:
    return []


def _get_downward_trace(db: Session, entity_type: str, entity_id: uuid.UUID) -> list:
    return []
