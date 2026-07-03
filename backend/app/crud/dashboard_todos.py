"""待我处理聚合：ECR/ECO 待我审批 + 我发起被驳回。只读，不写日志。"""
from sqlalchemy.orm import Session
from app.models.models_ecr import ECR, ECRReviewRecord
from app.models.models_eco import ECO, ECOReviewRecord


def _is_reviewer(reviewers, user_id_str):
    """检查 user_id 是否在 reviewers JSONB 列表中"""
    for r in reviewers or []:
        if str(r.get("user_id")) == user_id_str:
            return True
    return False


def _collect(db: Session, user_id, Model, RecordModel, type_name, number_attr, fk_col):
    """收集某类变更（ECR/ECO）中与 user_id 相关的待办"""
    uid = str(user_id)
    out = []
    # 待我审批：reviewing 状态且我是评审人且尚未评审
    reviewing = db.query(Model).filter(Model.status == "reviewing", Model.deleted_at.is_(None)).all()
    for m in reviewing:
        if not _is_reviewer(m.reviewers, uid):
            continue
        done = db.query(RecordModel).filter(
            fk_col == m.id,
            RecordModel.reviewer_id == user_id,
        ).first()
        if done:
            continue
        out.append(_row(m, type_name, number_attr, "review"))
    # 我发起被驳回
    rejected = db.query(Model).filter(
        Model.status == "rejected", Model.creator_id == user_id, Model.deleted_at.is_(None)
    ).all()
    for m in rejected:
        out.append(_row(m, type_name, number_attr, "rejected"))
    return out


def _row(m, type_name, number_attr, kind):
    return {
        "type": type_name,
        "kind": kind,
        "id": str(m.id),
        "number": getattr(m, number_attr),
        "title": m.title,
        "priority": m.priority,
        "status": m.status,
        "updated_at": m.updated_at.isoformat() if m.updated_at else None,
    }


def get_my_todos(db: Session, user_id):
    todos = []
    todos += _collect(db, user_id, ECR, ECRReviewRecord, "ecr", "ecr_number", ECRReviewRecord.ecr_id)
    todos += _collect(db, user_id, ECO, ECOReviewRecord, "eco", "eco_number", ECOReviewRecord.eco_id)
    todos.sort(key=lambda x: x["updated_at"] or "", reverse=True)
    return todos
