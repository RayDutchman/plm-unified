"""ChangeIssue CRUD 路由。"""
import uuid
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from app.database import get_db
from app.routers.auth import get_current_active_user
from app.models.user import User
from app.models.models_change_issue import ChangeIssue
from app.schemas.change_issue import IssueCreate, IssueUpdate, IssueResponse, IssueListResponse

router = APIRouter(prefix="/issues", tags=["变更问题"])


def _generate_issue_number(db: Session, workspace_id: uuid.UUID) -> str:
    """生成问题编号：ISSUE-{workspace_short}-XXXXXX"""
    count = (
        db.query(ChangeIssue).count() + 1
    )
    return f"ISSUE-{count:06d}"


@router.post("", response_model=IssueResponse, status_code=201, summary="创建问题")
def create_issue(
    data: IssueCreate,
    workspace_id: uuid.UUID = Query(..., description="工作空间 ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    issue = ChangeIssue(
        issue_number=_generate_issue_number(db, workspace_id),
        title=data.title,
        description=data.description,
        initiator=data.initiator,
        priority=data.priority,
        category=data.category,
        assignee_id=data.assignee_id,
        author_id=current_user.id,
        workspace_id=workspace_id,
        tags=data.tags,
        affected_parts=data.affected_parts,
        affected_documents=data.affected_documents,
        cc_users=data.cc_users,
    )
    db.add(issue)
    db.commit()
    db.refresh(issue)
    return issue


@router.get("", response_model=IssueListResponse, summary="问题列表")
def list_issues(
    workspace_id: uuid.UUID = Query(..., description="工作空间 ID"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    search: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    q = db.query(ChangeIssue).filter(
        ChangeIssue.workspace_id == workspace_id,
        ChangeIssue.deleted_at.is_(None),
    )
    if search:
        like = f"%{search}%"
        q = q.filter(
            (ChangeIssue.title.ilike(like)) |
            (ChangeIssue.issue_number.ilike(like)) |
            (ChangeIssue.description.ilike(like))
        )
    if status:
        q = q.filter(ChangeIssue.status == status)
    if priority:
        q = q.filter(ChangeIssue.priority == priority)

    total = q.count()
    items = q.order_by(ChangeIssue.created_at.desc()).offset(
        (page - 1) * page_size
    ).limit(page_size).all()

    return IssueListResponse(items=items, total=total, page=page, page_size=page_size)


@router.get("/{issue_id}", response_model=IssueResponse, summary="查询问题")
def get_issue(
    issue_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    issue = db.get(ChangeIssue, issue_id)
    if not issue or issue.deleted_at:
        raise HTTPException(404, "问题不存在")
    return issue


@router.put("/{issue_id}", response_model=IssueResponse, summary="更新问题")
def update_issue(
    issue_id: uuid.UUID,
    data: IssueUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    issue = db.get(ChangeIssue, issue_id)
    if not issue or issue.deleted_at:
        raise HTTPException(404, "问题不存在")

    update_fields = data.model_dump(exclude_unset=True)
    # 状态转换时记录时间
    for field, value in update_fields.items():
        if hasattr(issue, field):
            setattr(issue, field, value)

    if "status" in update_fields:
        if data.status == "resolved":
            issue.resolved_at = datetime.now(timezone.utc)
        elif data.status == "closed":
            issue.closed_at = datetime.now(timezone.utc)

    issue.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(issue)
    return issue


@router.delete("/{issue_id}", summary="删除问题（软删除）")
def delete_issue(
    issue_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    issue = db.get(ChangeIssue, issue_id)
    if not issue or issue.deleted_at:
        raise HTTPException(404, "问题不存在")
    issue.deleted_at = datetime.now(timezone.utc)
    db.commit()
    return {"detail": "已删除"}
