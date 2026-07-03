"""CRUD 聚合入口。"""
from typing import List, Union

from app.crud.user import get_user, get_user_by_username, get_users, authenticate_user, create_user, update_user, delete_user
from app.models import OperationLog


def create_log(
    db,
    user_id,
    username,
    action,
    target_type=None,
    target_id=None,
    detail=None,
    ip_address=None,
    id=None,
):
    db_log = OperationLog(
        user_id=user_id, username=username, action=action,
        target_type=target_type, target_id=target_id,
        detail=detail, ip_address=ip_address
    )
    if id:
        db_log.id = id
    db.add(db_log)
    db.commit()
    return db_log


def get_logs(db, skip=0, limit=100, target_type: Union[str, List[str], None] = None, target_id=None):
    q = db.query(OperationLog)
    if target_type:
        if isinstance(target_type, list):
            q = q.filter(OperationLog.target_type.in_(target_type))
        else:
            q = q.filter(OperationLog.target_type == target_type)
    if target_id:
        q = q.filter(OperationLog.target_id == target_id)
    total = q.count()
    items = q.order_by(OperationLog.created_at.desc()).offset(skip).limit(limit).all()
    return items, total
