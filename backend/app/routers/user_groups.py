from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
import uuid

from app.database import get_db
from app.models import User
from app.models.user_groups import UserGroup, user_group_members
from app.schemas.user_group import UserGroupCreate, UserGroupUpdate, GroupMembersUpdate
from app.permissions import require_permission

router = APIRouter(prefix="/user-groups", tags=["\u7528\u6237\u7ec4\u7ba1\u7406"])


def _group_dict(db, g):
    count = db.query(user_group_members).filter(user_group_members.c.group_id == g.id).count()
    return {"id": g.id, "name": g.name, "description": g.description,
            "member_count": count, "created_at": g.created_at, "updated_at": g.updated_at}


@router.get("/")
async def list_groups(db: Session = Depends(get_db),
                      current_user: User = Depends(require_permission("user_groups:read"))):
    groups = db.query(UserGroup).order_by(UserGroup.name).all()
    return [_group_dict(db, g) for g in groups]


@router.post("/")
async def create_group(body: UserGroupCreate, request: Request, db: Session = Depends(get_db),
                       current_user: User = Depends(require_permission("user_groups:manage"))):
    if db.query(UserGroup).filter(UserGroup.name == body.name).first():
        raise HTTPException(status_code=400, detail="\u8be5\u7528\u6237\u7ec4\u540d\u79f0\u5df2\u5b58\u5728")
    g = UserGroup(name=body.name, description=body.description)
    db.add(g)
    db.commit()
    db.refresh(g)
    return _group_dict(db, g)


@router.put("/{group_id}")
async def update_group(group_id: uuid.UUID, body: UserGroupUpdate, request: Request, db: Session = Depends(get_db),
                       current_user: User = Depends(require_permission("user_groups:manage"))):
    g = db.query(UserGroup).filter(UserGroup.id == group_id).first()
    if not g:
        raise HTTPException(status_code=404, detail="\u7528\u6237\u7ec4\u4e0d\u5b58\u5728")
    if body.name and body.name != g.name:
        if db.query(UserGroup).filter(UserGroup.name == body.name, UserGroup.id != group_id).first():
            raise HTTPException(status_code=400, detail="\u8be5\u7528\u6237\u7ec4\u540d\u79f0\u5df2\u5b58\u5728")
        g.name = body.name
    if body.description is not None:
        g.description = body.description
    db.commit()
    db.refresh(g)
    return _group_dict(db, g)


@router.delete("/{group_id}")
async def delete_group(group_id: uuid.UUID, request: Request, db: Session = Depends(get_db),
                       current_user: User = Depends(require_permission("user_groups:manage"))):
    g = db.query(UserGroup).filter(UserGroup.id == group_id).first()
    if not g:
        raise HTTPException(status_code=404, detail="\u7528\u6237\u7ec4\u4e0d\u5b58\u5728")
    db.execute(user_group_members.delete().where(user_group_members.c.group_id == group_id))
    db.delete(g)
    db.commit()
    return {"message": "\u7528\u6237\u7ec4\u5df2\u5220\u9664"}


@router.get("/{group_id}/members")
async def get_members(group_id: uuid.UUID, db: Session = Depends(get_db),
                      current_user: User = Depends(require_permission("user_groups:read"))):
    rows = db.query(user_group_members.c.user_id).filter(user_group_members.c.group_id == group_id).all()
    return {"user_ids": [r[0] for r in rows]}


@router.put("/{group_id}/members")
async def set_members(group_id: uuid.UUID, body: GroupMembersUpdate, request: Request, db: Session = Depends(get_db),
                      current_user: User = Depends(require_permission("user_groups:manage"))):
    g = db.query(UserGroup).filter(UserGroup.id == group_id).first()
    if not g:
        raise HTTPException(status_code=404, detail="\u7528\u6237\u7ec4\u4e0d\u5b58\u5728")
    db.execute(user_group_members.delete().where(user_group_members.c.group_id == group_id))
    uids = set(body.user_ids)
    if uids:
        db.execute(user_group_members.insert(), [{"user_id": uid, "group_id": group_id} for uid in uids])
    db.commit()
    return {"user_ids": list(uids)}
