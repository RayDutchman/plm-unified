"""
ECO (Engineering Change Order) - API Router
=============================================
变更管理 - ECO 模块 API 端点
"""
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User, PartMaster, PartRevision
from app.models.models_eco import ECO as ECOModel, ECOExecutionItem, ECOReviewRecord, ECOStatusLog
from app.permissions import require_permission, enforce_object_policy
from app.schemas.eco import (
    ECOCreate, ECOUpdate, ECOListParams, ECOReviewAction, ECOCcAction,
    ECOExecutionItemCreate, ECOExecutionItemEdit, ECOExecutionItemAction,
)
from app.crud.eco import (
    create_eco, get_ecos, get_eco, update_eco, delete_eco,
    change_eco_status, add_eco_review_record, check_all_approved, clear_review_records,
    add_execution_item, get_execution_items, get_execution_item,
    update_execution_item, remove_execution_item,
    add_cc_users, remove_cc_user, get_status_logs,
    execute_item, execute_all,
)

router = APIRouter(prefix="/ecos", tags=["变更管理-ECO"])


def _build_eco_detail(db: Session, eco: ECOModel) -> dict:
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

    reviewers_detail = []
    for r in (eco.reviewers or []):
        reviewers_detail.append({
            "seq": r.get("seq", 0), "user_id": r.get("user_id", ""),
            "user_name": r.get("user_name", ""), "role": r.get("role", ""),
        })

    review_records = db.query(ECOReviewRecord).filter(
        ECOReviewRecord.eco_id == eco.id
    ).order_by(ECOReviewRecord.created_at).all()
    review_record_items = [
        {"id": str(r.id), "reviewer_id": str(r.reviewer_id),
         "reviewer_name": r.reviewer_name or "", "decision": r.decision,
         "comment": r.comment, "created_at": r.created_at}
        for r in review_records
    ]

    status_logs = db.query(ECOStatusLog).filter(
        ECOStatusLog.eco_id == eco.id
    ).order_by(ECOStatusLog.created_at).all()
    status_log_items = [
        {"id": str(l.id), "from_status": l.from_status, "to_status": l.to_status,
         "operator_name": l.operator_name or "", "comment": l.comment,
         "created_at": l.created_at}
        for l in status_logs
    ]

    execution_items = db.query(ECOExecutionItem).filter(
        ECOExecutionItem.eco_id == eco.id
    ).order_by(ECOExecutionItem.sort_order).all()
    execution_item_list = []
    for ei in execution_items:
        entity_version = ei.entity_version or ""
        if ei.entity_id:
            ent = db.query(PartMaster).filter(PartMaster.id == ei.entity_id).first()
            if ent:
                entity_version = entity_version or ""

        new_entity_status = None
        if ei.new_entity_id:
            new_ent = db.query(PartRevision).filter(PartRevision.id == ei.new_entity_id).first()
            if new_ent:
                new_entity_status = new_ent.status

        execution_item_list.append({
            "id": str(ei.id), "source": ei.source, "entity_type": ei.entity_type,
            "entity_id": str(ei.entity_id) if ei.entity_id else None,
            "entity_code": ei.entity_code or "", "entity_name": ei.entity_name,
            "entity_version": entity_version,
            "action": ei.action, "status": ei.status, "detail": ei.detail or {},
            "new_entity_id": str(ei.new_entity_id) if ei.new_entity_id else None,
            "new_version": ei.new_version,
            "new_entity_status": new_entity_status,
            "parent_entity_id": str(ei.parent_entity_id) if ei.parent_entity_id else None,
            "parent_new_entity_id": str(ei.parent_new_entity_id) if ei.parent_new_entity_id else None,
            "error_message": ei.error_message, "sort_order": ei.sort_order,
            "executed_at": ei.executed_at}
        )

    ecr_number = None
    if eco.ecr_id:
        from app.models.models_ecr import ECR as ECRModel
        ecr_obj = db.query(ECRModel).filter(ECRModel.id == eco.ecr_id).first()
        if ecr_obj:
            ecr_number = ecr_obj.ecr_number

    return {
        "id": eco.id, "eco_number": eco.eco_number, "title": eco.title,
        "status": eco.status, "priority": eco.priority, "category": eco.category,
        "creator_name": creator_name, "reviewers_count": reviewers_count,
        "approved_count": approved_count, "execution_count": execution_count,
        "execution_completed_count": execution_completed_count,
        "ecr_id": str(eco.ecr_id) if eco.ecr_id else None, "ecr_number": ecr_number,
        "created_at": eco.created_at, "updated_at": eco.updated_at,
        "description": eco.description, "reason": eco.reason,
        "review_mode": eco.review_mode, "reviewers": reviewers_detail,
        "review_records": review_record_items,
        "document_links": eco.document_links or [],
        "execution_items": execution_item_list,
        "status_logs": status_log_items,
        "cc_users": eco.cc_users or [],
        "release_items": eco.release_items or [],
        "reviewed_at": eco.reviewed_at, "executed_at": eco.executed_at,
        "closed_at": eco.closed_at,
    }


@router.get("/")
async def list_ecos(
    page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
    search: str = Query(None), status: str = Query(None), priority: str = Query(None),
    updated_since: float = Query(None, description="仅返回指定 UNIX 时间戳之后更新的记录（含已删除）"),
    brief: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("eco:read"))
):
    params = ECOListParams(page=page, page_size=page_size, search=search, status=status, priority=priority)
    include_deleted = bool(updated_since)
    items, total = get_ecos(db, params, current_user, include_deleted=include_deleted, updated_since=updated_since)

    if brief:
        brief_items = [
            {
                "id": str(item["id"]),
                "eco_number": item["eco_number"],
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
        s = {**item, "id": str(item["id"])}
        s["ecr_id"] = str(s["ecr_id"]) if s.get("ecr_id") else None
        items_serialized.append(s)
    return {"items": items_serialized, "total": total, "page": page, "page_size": page_size}


@router.post("/")
async def create_eco_endpoint(
    data: ECOCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("eco:create"))
):
    eco = create_eco(db, data, current_user.id)
    return _build_eco_detail(db, eco)


@router.get("/{eco_id}")
async def get_eco_detail(
    eco_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("eco:read"))
):
    eco = get_eco(db, eco_id)
    return _build_eco_detail(db, eco)


@router.put("/{eco_id}")
async def update_eco_endpoint(
    eco_id: uuid.UUID, data: ECOUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("eco:update"))
):
    eco = get_eco(db, eco_id)
    enforce_object_policy("eco_owner_or_admin", current_user, eco)
    update_eco(db, eco, data)
    return _build_eco_detail(db, eco)


@router.delete("/{eco_id}")
async def delete_eco_endpoint(
    eco_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("eco:delete"))
):
    eco = get_eco(db, eco_id)
    enforce_object_policy("eco_owner_or_admin", current_user, eco)
    if eco.status != "draft":
        raise HTTPException(status_code=400, detail="仅草稿状态的 ECO 可以删除")
    delete_eco(db, eco_id)
    return {"detail": "已删除"}


@router.post("/{eco_id}/submit")
async def submit_eco(
    eco_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("eco:submit"))
):
    eco = get_eco(db, eco_id)
    enforce_object_policy("eco_owner_or_admin", current_user, eco)
    if eco.status != "draft":
        raise HTTPException(status_code=400, detail="仅草稿状态可提交评审")
    clear_review_records(db, eco_id)

    if not eco.reviewers or len(eco.reviewers) == 0:
        eco = change_eco_status(db, eco_id, "approved", current_user.id, "无审批人，自动批准")
    else:
        eco = change_eco_status(db, eco_id, "reviewing", current_user.id, "提交评审")
    return _build_eco_detail(db, eco)


@router.post("/{eco_id}/withdraw")
async def withdraw_eco(
    eco_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("eco:withdraw"))
):
    eco = get_eco(db, eco_id)
    enforce_object_policy("eco_owner_or_admin", current_user, eco)
    if eco.status != "reviewing":
        raise HTTPException(status_code=400, detail="仅评审中状态可撤回")
    clear_review_records(db, eco_id)
    eco = change_eco_status(db, eco_id, "draft", current_user.id, "撤回评审")
    return _build_eco_detail(db, eco)


@router.post("/{eco_id}/review")
async def review_eco(
    eco_id: uuid.UUID,
    data: ECOReviewAction,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("eco:approve"))
):
    eco = get_eco(db, eco_id)
    if eco.status != "reviewing":
        raise HTTPException(status_code=400, detail="ECO 不在评审中状态")

    reviewer_ids = set()
    for r in (eco.reviewers or []):
        try:
            reviewer_ids.add(uuid.UUID(r["user_id"]))
        except (ValueError, KeyError):
            pass

    enforce_object_policy("eco_approver_or_admin", current_user, eco, reviewer_ids=reviewer_ids)

    if data.decision == "returned":
        clear_review_records(db, eco_id)
        eco = change_eco_status(db, eco_id, "draft", current_user.id, data.comment or "退回修改")
        return _build_eco_detail(db, eco)

    add_eco_review_record(db, eco_id, current_user.id, data.decision, data.comment)

    decision_labels = {"approved": "审批通过", "rejected": "审批驳回"}
    if data.decision in decision_labels:
        log = ECOStatusLog(
            eco_id=eco_id, from_status=eco.status, to_status=eco.status,
            operator_id=current_user.id, operator_name=current_user.real_name,
            comment=f"{decision_labels[data.decision]}" + (f": {data.comment}" if data.comment else ""),
        )
        db.add(log)
        db.commit()

    if data.decision == "approved":
        if check_all_approved(db, eco_id):
            change_eco_status(db, eco_id, "approved", current_user.id, "所有审批人已通过", skip_log=True)
    elif data.decision == "rejected":
        change_eco_status(db, eco_id, "rejected", current_user.id, data.comment or "驳回")

    db.refresh(eco)
    return _build_eco_detail(db, eco)


@router.post("/{eco_id}/execute")
async def start_execution(
    eco_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("eco:execute"))
):
    eco = get_eco(db, eco_id)
    if eco.status != "approved":
        raise HTTPException(status_code=400, detail="仅已批准状态可执行")
    eco = change_eco_status(db, eco_id, "executing", current_user.id, "开始执行")
    return _build_eco_detail(db, eco)


@router.post("/{eco_id}/complete")
async def complete_execution(
    eco_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("eco:close"))
):
    eco = get_eco(db, eco_id)
    if eco.status != "executing":
        raise HTTPException(status_code=400, detail="仅执行中状态可完成执行")
    eco = change_eco_status(db, eco_id, "completed", current_user.id, "手动完成执行")
    return _build_eco_detail(db, eco)


@router.post("/{eco_id}/execute-item/{item_id}")
async def execute_single_item(
    eco_id: uuid.UUID, item_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("eco:execute_item"))
):
    eco = get_eco(db, eco_id)
    if eco.status not in ("executing", "approved"):
        raise HTTPException(status_code=400, detail="仅已批准或执行中状态可执行")
    if eco.status == "approved":
        change_eco_status(db, eco_id, "executing", current_user.id, "开始执行")
    item = get_execution_item(db, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="执行项不存在")
    execute_item(db, item)
    return _build_eco_detail(db, get_eco(db, eco_id))


@router.post("/{eco_id}/execute-all")
async def execute_all_items(
    eco_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("eco:execute_all"))
):
    eco = get_eco(db, eco_id)
    if eco.status not in ("approved", "executing"):
        raise HTTPException(status_code=400, detail="仅已批准或执行中状态可一键执行")
    if eco.status == "approved":
        change_eco_status(db, eco_id, "executing", current_user.id, "开始一键执行")
    results = execute_all(db, eco)
    return {"results": results, "eco": _build_eco_detail(db, get_eco(db, eco_id))}


@router.get("/{eco_id}/execution-items")
async def list_execution_items(
    eco_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("eco:read"))
):
    items = get_execution_items(db, eco_id)
    serialized = []
    for ei in items:
        serialized.append({
            "id": str(ei.id), "source": ei.source, "entity_type": ei.entity_type,
            "entity_id": str(ei.entity_id) if ei.entity_id else None,
            "entity_code": ei.entity_code or "", "entity_name": ei.entity_name,
            "action": ei.action, "status": ei.status, "detail": ei.detail or {},
            "new_entity_id": str(ei.new_entity_id) if ei.new_entity_id else None,
            "new_version": ei.new_version,
            "parent_entity_id": str(ei.parent_entity_id) if ei.parent_entity_id else None,
            "parent_new_entity_id": str(ei.parent_new_entity_id) if ei.parent_new_entity_id else None,
            "error_message": ei.error_message, "sort_order": ei.sort_order,
            "executed_at": ei.executed_at,
        })
    return {"items": serialized}


@router.post("/{eco_id}/execution-items")
async def add_execution_item_endpoint(
    eco_id: uuid.UUID, data: ECOExecutionItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("eco.affected:manage"))
):
    eco = get_eco(db, eco_id)
    if eco.status != "draft":
        raise HTTPException(status_code=400, detail="仅草稿状态可添加执行项")
    item = add_execution_item(db, eco, data)
    return {
        "id": str(item.id), "source": item.source, "entity_type": item.entity_type,
        "entity_name": item.entity_name, "action": item.action, "status": item.status,
        "sort_order": item.sort_order,
    }


@router.put("/{eco_id}/execution-items/{item_id}")
async def edit_execution_item_endpoint(
    eco_id: uuid.UUID, item_id: uuid.UUID,
    data: ECOExecutionItemEdit,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("eco.affected:manage"))
):
    eco = get_eco(db, eco_id)
    if eco.status != "draft":
        raise HTTPException(status_code=400, detail="仅草稿状态可编辑执行项")
    exec_item = db.query(ECOExecutionItem).filter(
        ECOExecutionItem.id == item_id, ECOExecutionItem.eco_id == eco_id
    ).first()
    if not exec_item:
        raise HTTPException(status_code=404, detail="执行项不存在")
    item = update_execution_item(db, exec_item, data)
    return {
        "id": str(item.id), "entity_name": item.entity_name,
        "action": item.action, "status": item.status, "sort_order": item.sort_order,
    }


@router.delete("/{eco_id}/execution-items/{item_id}")
async def remove_execution_item_endpoint(
    eco_id: uuid.UUID, item_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("eco.affected:manage"))
):
    eco = get_eco(db, eco_id)
    if eco.status != "draft":
        raise HTTPException(status_code=400, detail="仅草稿状态可删除执行项")
    remove_execution_item(db, eco_id, item_id)
    return {"detail": "已删除"}


@router.post("/{eco_id}/execution-items/{item_id}/upgrade")
async def manual_upgrade_item(
    eco_id: uuid.UUID, item_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("eco:revise"))
):
    from app.crud.eco import _upgrade_entity, _next_version_str

    item = get_execution_item(db, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="执行项不存在")
    if not item.entity_id:
        raise HTTPException(status_code=400, detail="执行项缺少 entity_id")

    entity = db.query(PartMaster).filter(PartMaster.id == item.entity_id).first()
    if not entity:
        raise HTTPException(status_code=404, detail="实体不存在")

    new_id, new_version = _upgrade_entity(db, item.entity_type, item.entity_id)
    db.commit()
    item.new_entity_id = new_id
    item.new_version = new_version
    item.detail = {**(item.detail or {}), "new_entity_id": str(new_id), "new_version": new_version}
    db.commit()
    return {"new_entity_id": str(new_id), "new_version": new_version}


@router.post("/{eco_id}/execution-items/{item_id}/revert")
async def manual_revert_item(
    eco_id: uuid.UUID, item_id: uuid.UUID,
    body: ECOExecutionItemAction = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("eco:restore"))
):
    from app.crud.eco import _revert_entity

    item = get_execution_item(db, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="执行项不存在")

    target_entity_id = item.new_entity_id or (uuid.UUID(body.new_entity_id) if body and body.new_entity_id else None)
    if not target_entity_id:
        raise HTTPException(status_code=400, detail="尚未执行升版，无需还原")

    new_entity = db.query(PartRevision).filter(PartRevision.id == target_entity_id).first()

    if not new_entity:
        item.new_entity_id = None
        item.new_version = None
        item.detail = {**(item.detail or {}), "new_entity_id": "", "new_version": ""}
        db.commit()
        return {"detail": "已还原"}

    if new_entity.status == "RELEASED":
        raise HTTPException(status_code=400, detail="已发布的零部件不可还原")
    if new_entity.status == "WIP":
        db.delete(new_entity)
        item.new_entity_id = None
        item.new_version = None
        item.detail = {**(item.detail or {}), "new_entity_id": "", "new_version": ""}
    else:
        new_entity.status = "WIP"

    db.commit()
    return {"detail": "已还原"}


@router.post("/{eco_id}/execution-items/{item_id}/freeze")
async def manual_freeze_item(
    eco_id: uuid.UUID, item_id: uuid.UUID,
    body: ECOExecutionItemAction = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("eco:freeze"))
):
    from app.crud.eco import _freeze_entity

    item = get_execution_item(db, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="执行项不存在")

    target_entity_id = item.new_entity_id or (uuid.UUID(body.new_entity_id) if body and body.new_entity_id else None)
    if not target_entity_id:
        raise HTTPException(status_code=400, detail="尚未执行升版，无法冻结")

    _freeze_entity(db, item.entity_type, target_entity_id)
    if not item.new_entity_id and target_entity_id:
        item.new_entity_id = target_entity_id
    db.commit()
    return {"detail": "已冻结"}


@router.post("/{eco_id}/execution-items/{item_id}/release")
async def manual_release_item(
    eco_id: uuid.UUID, item_id: uuid.UUID,
    body: ECOExecutionItemAction = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("eco:publish"))
):
    from app.crud.eco import _release_entity

    item = get_execution_item(db, item_id)
    if not item:
        raise HTTPException(status_code=404, detail="执行项不存在")

    target_entity_id = item.new_entity_id or (uuid.UUID(body.new_entity_id) if body and body.new_entity_id else None)
    if not target_entity_id:
        raise HTTPException(status_code=400, detail="尚未执行升版，无法发布")

    _release_entity(db, item.entity_type, target_entity_id)
    db.commit()
    return {"detail": "已发布"}


@router.get("/{eco_id}/status-logs")
async def get_eco_status_logs(
    eco_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("eco:read_status_log"))
):
    logs = get_status_logs(db, eco_id)
    serialized = [
        {"id": str(l.id), "from_status": l.from_status, "to_status": l.to_status,
         "operator_name": l.operator_name or "", "comment": l.comment, "created_at": l.created_at}
        for l in logs
    ]
    return {"items": serialized}


@router.post("/{eco_id}/cc")
async def cc_users_endpoint(
    eco_id: uuid.UUID, data: ECOCcAction,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("eco:cc_manage"))
):
    eco = get_eco(db, eco_id)
    add_cc_users(db, eco, data.user_ids)
    return {"detail": "已添加知会"}


@router.delete("/{eco_id}/cc/{user_id}")
async def uncc_user_endpoint(
    eco_id: uuid.UUID, user_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("eco:cc_manage"))
):
    eco = get_eco(db, eco_id)
    remove_cc_user(db, eco, str(user_id))
    return {"detail": "已取消知会"}


@router.post("/{eco_id}/bom-trace/{entity_type}/{entity_id}")
async def bom_trace(
    eco_id: uuid.UUID, entity_type: str, entity_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("eco:bom_trace"))
):
    try:
        from app.crud.ecr import _get_upward_trace, _get_downward_trace
        upward = _get_upward_trace(db, entity_type, entity_id)
        downward = _get_downward_trace(db, entity_type, entity_id)
        return {"upward_chain": upward, "downward_items": downward}
    except Exception:
        return {"upward_chain": [], "downward_items": []}
