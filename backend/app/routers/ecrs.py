"""
ECR (Engineering Change Request) - API Router
==============================================
变更管理 - ECR 模块 API 端点
"""
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, Component, PartMaster
from app.models.models_ecr import ECR as ECRModel, ECRReviewRecord, ECRStatusLog, ECRAffectedItem
from app.routers.auth import get_current_active_user
from app.schemas.ecr import (
    ECRCreate, ECRUpdate, ECRListParams, ECRReviewAction, ECRCloseAction, ECRAffectedItemCreate,
)
from app.crud.ecr import (
    create_ecr, get_ecrs, get_ecr, update_ecr, delete_ecr,
    change_ecr_status, add_ecr_review_record, check_all_approved,
    add_affected_item, get_affected_items, delete_affected_item,
    _get_upward_trace, _get_downward_trace,
)

router = APIRouter(prefix="/ecrs", tags=["变更管理"])


def _check_owner_or_admin(current_user, ecr):
    if current_user.role != "admin" and ecr.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权操作该对象")


def _build_ecr_detail(db: Session, ecr: ECRModel) -> dict:
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

    reviewers_detail = []
    for r in (ecr.reviewers or []):
        reviewers_detail.append({
            "seq": r.get("seq", 0),
            "user_id": r.get("user_id", ""),
            "user_name": r.get("user_name", ""),
            "role": r.get("role", ""),
        })

    review_records = db.query(ECRReviewRecord).filter(
        ECRReviewRecord.ecr_id == ecr.id
    ).order_by(ECRReviewRecord.created_at).all()
    review_record_items = [
        {
            "id": str(r.id),
            "reviewer_id": str(r.reviewer_id),
            "reviewer_name": r.reviewer_name or "",
            "decision": r.decision,
            "comment": r.comment,
            "created_at": r.created_at,
        }
        for r in review_records
    ]

    status_logs = db.query(ECRStatusLog).filter(
        ECRStatusLog.ecr_id == ecr.id
    ).order_by(ECRStatusLog.created_at).all()
    status_log_items = [
        {
            "id": str(log.id),
            "from_status": log.from_status,
            "to_status": log.to_status,
            "operator_name": log.operator_name or "",
            "comment": log.comment,
            "created_at": log.created_at,
        }
        for log in status_logs
    ]

    affected_items_data = get_affected_items(db, ecr.id)
    affected_item_list = [
        {
            "id": str(item.id),
            "entity_type": item.entity_type,
            "entity_id": str(item.entity_id),
            "entity_code": item.entity_code or "",
            "entity_name": item.entity_name or "",
            "entity_version": item.entity_version or "",
            "change_description": item.change_description,
            "change_type": item.change_type,
            "bom_impact": item.bom_impact or {},
        }
        for item in affected_items_data
    ]

    return {
        "id": ecr.id,
        "ecr_number": ecr.ecr_number,
        "title": ecr.title,
        "status": ecr.status,
        "priority": ecr.priority,
        "category": ecr.category,
        "creator_name": creator_name,
        "reviewers_count": reviewers_count,
        "approved_count": approved_count,
        "affected_count": affected_count,
        "created_at": ecr.created_at,
        "updated_at": ecr.updated_at,
        "description": ecr.description,
        "reason": ecr.reason,
        "review_mode": ecr.review_mode,
        "reviewers": reviewers_detail,
        "review_records": review_record_items,
        "document_links": ecr.document_links or [],
        "cc_users": ecr.cc_users or [],
        "affected_items": affected_item_list,
        "status_logs": status_log_items,
        "reviewed_at": ecr.reviewed_at,
        "closed_at": ecr.closed_at,
        "eco_id": str(ecr.eco_id) if ecr.eco_id else None,
    }


@router.get("/")
async def list_ecrs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: str = Query(None),
    status: str = Query(None),
    priority: str = Query(None),
    updated_since: float = Query(None),
    brief: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    params = ECRListParams(
        page=page, page_size=page_size,
        search=search, status=status, priority=priority
    )
    include_deleted = bool(updated_since)
    items, total = get_ecrs(db, params, current_user, include_deleted=include_deleted, updated_since=updated_since)

    if brief:
        brief_items = [
            {
                "id": str(item["id"]),
                "ecr_number": item["ecr_number"],
                "title": item["title"],
                "status": item["status"],
                "priority": item["priority"],
                "creator_name": item["creator_name"],
                "updated_at": item["updated_at"],
                "deleted_at": item.get("deleted_at"),
            }
            for item in items
        ]
        return {"items": brief_items, "total": total, "page": page, "page_size": page_size}

    items_serialized = []
    for item in items:
        serialized = {**item}
        serialized["id"] = str(serialized["id"])
        serialized["creator_id"] = str(serialized["creator_id"]) if serialized.get("creator_id") else None
        items_serialized.append(serialized)
    return {
        "items": items_serialized,
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/")
async def create_ecr_endpoint(
    data: ECRCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    ecr = create_ecr(db, data, current_user.id)
    return _build_ecr_detail(db, ecr)


@router.get("/{ecr_id}")
async def get_ecr_detail(
    ecr_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    ecr = get_ecr(db, ecr_id)
    return _build_ecr_detail(db, ecr)


@router.put("/{ecr_id}")
async def update_ecr_endpoint(
    ecr_id: uuid.UUID,
    data: ECRUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    ecr = get_ecr(db, ecr_id)
    _check_owner_or_admin(current_user, ecr)
    ecr = update_ecr(db, ecr_id, data)
    return _build_ecr_detail(db, ecr)


@router.delete("/{ecr_id}")
async def delete_ecr_endpoint(
    ecr_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    # ECO 引用检查将在 ECO 模块迁移后启用
    ecr = get_ecr(db, ecr_id)
    _check_owner_or_admin(current_user, ecr)
    if not delete_ecr(db, ecr_id):
        raise HTTPException(status_code=404, detail="ECR 不存在或已删除")
    return {"message": "ECR 已删除"}


@router.post("/{ecr_id}/submit")
async def submit_ecr(
    ecr_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    ecr = get_ecr(db, ecr_id)
    _check_owner_or_admin(current_user, ecr)
    if ecr.status != "draft":
        raise HTTPException(status_code=400, detail="仅草稿状态的 ECR 可以提交评审")

    if not ecr.reviewers or len(ecr.reviewers) == 0:
        raise HTTPException(status_code=400, detail="请设置至少一位审批人")

    ecr = change_ecr_status(
        db, ecr_id, "reviewing", current_user.id, "提交评审"
    )
    return _build_ecr_detail(db, ecr)


@router.post("/{ecr_id}/withdraw")
async def withdraw_ecr(
    ecr_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    ecr = get_ecr(db, ecr_id)
    _check_owner_or_admin(current_user, ecr)
    if ecr.status != "reviewing":
        raise HTTPException(status_code=400, detail="仅评审中状态的 ECR 可以撤回")
    if ecr.creator_id != current_user.id and current_user.role != "admin":
        raise HTTPException(status_code=403, detail="仅创建人或管理员可以撤回")
    db.query(ECRReviewRecord).filter(
        ECRReviewRecord.ecr_id == ecr_id
    ).delete()
    ecr = change_ecr_status(
        db, ecr_id, "draft", current_user.id, "撤回评审"
    )
    return _build_ecr_detail(db, ecr)


@router.post("/{ecr_id}/review")
async def review_ecr(
    ecr_id: uuid.UUID,
    data: ECRReviewAction,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    ecr = get_ecr(db, ecr_id)
    if ecr.status != "reviewing":
        raise HTTPException(status_code=400, detail="仅评审中状态的 ECR 可进行审批")

    reviewer_ids = set()
    for r in (ecr.reviewers or []):
        try:
            reviewer_ids.add(uuid.UUID(r["user_id"]))
        except (ValueError, KeyError):
            pass

    if current_user.role != "admin" and current_user.id not in reviewer_ids:
        raise HTTPException(status_code=403, detail="您不是该 ECR 的指定审批人")

    if data.decision == "returned":
        db.query(ECRReviewRecord).filter(
            ECRReviewRecord.ecr_id == ecr_id
        ).delete()
        change_ecr_status(
            db, ecr_id, "draft", current_user.id,
            comment=data.comment or "退回修改"
        )
        db.refresh(ecr)
        return _build_ecr_detail(db, ecr)

    add_ecr_review_record(
        db, ecr_id, current_user.id, data.decision, data.comment
    )

    decision_labels = {"approved": "审批通过", "rejected": "审批驳回"}
    if data.decision in decision_labels:
        log = ECRStatusLog(
            ecr_id=ecr_id,
            from_status=ecr.status,
            to_status=ecr.status,
            operator_id=current_user.id,
            operator_name=current_user.real_name,
            comment=f"{decision_labels[data.decision]}" + (f": {data.comment}" if data.comment else ""),
        )
        db.add(log)
        db.commit()

    if data.decision == "approved":
        if check_all_approved(db, ecr_id):
            change_ecr_status(
                db, ecr_id, "approved", current_user.id,
                comment="所有审批人已通过，自动批准"
            )
    elif data.decision == "rejected":
        change_ecr_status(
            db, ecr_id, "rejected", current_user.id,
            comment=data.comment or "审批驳回"
        )

    db.refresh(ecr)
    return _build_ecr_detail(db, ecr)


@router.post("/{ecr_id}/close")
async def close_ecr(
    ecr_id: uuid.UUID,
    data: ECRCloseAction = ECRCloseAction(),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    ecr = get_ecr(db, ecr_id)
    if ecr.status not in ("approved", "rejected", "draft"):
        raise HTTPException(status_code=400, detail="当前状态不允许关闭")

    ecr = change_ecr_status(
        db, ecr_id, "closed", current_user.id,
        comment=data.comment or "关闭"
    )
    return _build_ecr_detail(db, ecr)


@router.post("/{ecr_id}/affected-items")
async def add_affected_item_endpoint(
    ecr_id: uuid.UUID,
    data: ECRAffectedItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    item = add_affected_item(db, ecr_id, data)
    return {
        "id": str(item.id),
        "entity_type": item.entity_type,
        "entity_id": str(item.entity_id),
        "entity_code": item.entity_code or "",
        "entity_name": item.entity_name or "",
        "entity_version": item.entity_version or "",
        "change_description": item.change_description,
        "change_type": item.change_type,
        "bom_impact": item.bom_impact or {},
    }


@router.delete("/{ecr_id}/affected-items/{item_id}")
async def remove_affected_item(
    ecr_id: uuid.UUID,
    item_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    delete_affected_item(db, item_id)
    return {"message": "受影响对象已移除"}


@router.put("/{ecr_id}/affected-items/{item_id}")
async def update_affected_item(
    ecr_id: uuid.UUID,
    item_id: uuid.UUID,
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    item = db.query(ECRAffectedItem).filter(
        ECRAffectedItem.id == item_id,
        ECRAffectedItem.ecr_id == ecr_id
    ).first()
    if not item:
        raise HTTPException(status_code=404, detail="受影响对象不存在")
    if data.get("bom_impact"):
        item.bom_impact = data["bom_impact"]
    if data.get("change_description") is not None:
        item.change_description = data["change_description"]
    if data.get("change_type"):
        item.change_type = data["change_type"]
    db.commit()
    return {"message": "已更新", "id": str(item.id)}


@router.get("/{ecr_id}/status-logs")
async def get_status_logs(
    ecr_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    logs = db.query(ECRStatusLog).filter(
        ECRStatusLog.ecr_id == ecr_id
    ).order_by(ECRStatusLog.created_at).all()
    return [
        {
            "id": str(log.id),
            "from_status": log.from_status,
            "to_status": log.to_status,
            "operator_name": log.operator_name or "",
            "comment": log.comment,
            "created_at": log.created_at,
        }
        for log in logs
    ]


@router.post("/{ecr_id}/bom-trace/{entity_type}/{entity_id}")
async def get_bom_trace(
    ecr_id: uuid.UUID,
    entity_type: str,
    entity_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    if entity_type not in ("part", "assembly"):
        raise HTTPException(status_code=400, detail="仅支持 part 或 assembly")

    if entity_type == "part":
        obj = db.query(PartMaster).filter(PartMaster.id == entity_id).first()
    else:
        obj = db.query(Component).filter(Component.id == entity_id).first()
    if not obj:
        raise HTTPException(status_code=404, detail="实体不存在")

    return {
        "upward_chain": _get_upward_trace(db, entity_type, entity_id),
        "downward_items": _get_downward_trace(db, entity_type, entity_id),
    }


@router.post("/{ecr_id}/cc")
async def cc_ecr(
    ecr_id: uuid.UUID,
    data: dict,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    ecr = get_ecr(db, ecr_id)
    user_ids = data.get("user_ids", [])
    if not user_ids:
        raise HTTPException(status_code=400, detail="请选择要知会的用户")

    cc_list = list(ecr.cc_users or [])
    existing = {c["user_id"] for c in cc_list}
    for uid in user_ids:
        if uid not in existing:
            user = db.query(User).filter(User.id == uid).first()
            if user:
                cc_list.append({"user_id": str(user.id), "user_name": user.real_name})

    ecr.cc_users = cc_list
    db.commit()
    return {"message": "知会成功", "cc_users": cc_list}


@router.delete("/{ecr_id}/cc/{user_id}")
async def uncc_ecr(
    ecr_id: uuid.UUID,
    user_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    ecr = get_ecr(db, ecr_id)
    cc_list = list(ecr.cc_users or [])
    uid = str(user_id)
    ecr.cc_users = [c for c in cc_list if c["user_id"] != uid]
    db.commit()
    return {"message": "取消知会成功", "cc_users": ecr.cc_users}
