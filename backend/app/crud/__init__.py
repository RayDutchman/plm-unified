"""CRUD 聚合入口。"""
from app.crud.user import get_user, get_user_by_username, get_users, authenticate_user, create_user, update_user, delete_user


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
    pass
