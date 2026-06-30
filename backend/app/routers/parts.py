"""零件 API 路由。

端点清单（M1.6 / M1.7）：
  POST   /api/parts                             创建零件（三层原子）
  GET    /api/parts                             列表（按 workspace_id 过滤，分页）
  GET    /api/parts/{number}                    查单个零件（含版本/迭代）
  PUT    /api/parts/{number}/{version}/checkout 签出
  PUT    /api/parts/{number}/{version}/checkin  签入
  PUT    /api/parts/{number}/{version}/undocheckout 撤销签出
"""
from __future__ import annotations

import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.crud.part import (
    checkin,
    checkout,
    create_part,
    get_part,
    list_parts,
    undocheckout,
)
from app.database import get_db
from app.models import User
from app.models.part import PartMaster
from app.routers.auth import get_current_active_user
from app.schemas.part import (
    CheckoutResponse,
    PartCreate,
    PartListItem,
    PartResponse,
)

router = APIRouter(prefix="/api/parts", tags=["零件管理"])


# ---------------------------------------------------------------------------
# 1.6 CRUD 端点
# ---------------------------------------------------------------------------

@router.post("", response_model=PartResponse, status_code=201, summary="创建零件")
def create_part_endpoint(
    data: PartCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    原子创建三层：PartMaster + PartRevision(A, WIP) + PartIteration(1)。
    创建后自动处于签出状态，需调用 checkin 才能冻结首个迭代。
    """
    master = create_part(db, data, author_id=current_user.id)
    return _enrich_response(db, master)


@router.get("", response_model=list[PartListItem], summary="零件列表")
def list_parts_endpoint(
    workspace_id: uuid.UUID = Query(..., description="工作空间 ID"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    列出工作空间内所有未删除的零件，附最新版本状态。
    """
    from app.models.part import PartRevision  # 避免循环导入
    masters = list_parts(db, workspace_id=workspace_id, skip=skip, limit=limit)
    result = []
    for m in masters:
        # 取最新版本（version 字母倒序取第一）
        rev = (
            db.query(PartRevision)
            .filter(
                PartRevision.part_master_id == m.id,
                PartRevision.deleted_at.is_(None),
            )
            .order_by(PartRevision.version.desc())
            .first()
        )
        item = PartListItem.model_validate(m)
        if rev:
            item.latest_version = rev.version
            item.latest_status = rev.status
            item.checkout_user_id = rev.checkout_user_id
        result.append(item)
    return result


@router.get("/{identifier}", response_model=PartResponse, summary="查询单个零件")
def get_part_endpoint(
    identifier: str,
    workspace_id: uuid.UUID = Query(..., description="工作空间 ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    返回零件主数据及其全部版本和迭代信息。
    支持按编号（number）或 UUID（id）查询。
    """
    # 尝试 UUID 解析
    try:
        uid = uuid.UUID(identifier)
        master = db.query(PartMaster).filter(
            PartMaster.id == uid,
            PartMaster.deleted_at.is_(None),
        ).first()
        if master:
            return _enrich_response(db, master)
    except ValueError:
        pass
    # 按 number 查
    master = get_part(db, number=identifier, workspace_id=workspace_id)
    return _enrich_response(db, master)


# ---------------------------------------------------------------------------
# 1.7 签入签出端点
# ---------------------------------------------------------------------------

@router.put("/{number}/{version}/checkout", response_model=CheckoutResponse, summary="签出")
def checkout_endpoint(
    number: str,
    version: str,
    workspace_id: uuid.UUID = Query(..., description="工作空间 ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    签出零件版本（加行锁）。
    - 409 若已被任何人签出
    - 409 若版本不是 WIP 状态
    """
    revision = checkout(
        db,
        number=number,
        version=version,
        workspace_id=workspace_id,
        current_user_id=current_user.id,
    )
    return CheckoutResponse(
        number=number,
        version=revision.version,
        status=revision.status,
        checkout_user_id=revision.checkout_user_id,
        checkout_date=revision.checkout_date,
        message="签出成功",
    )


@router.put("/{number}/{version}/checkin", response_model=CheckoutResponse, summary="签入")
def checkin_endpoint(
    number: str,
    version: str,
    workspace_id: uuid.UUID = Query(..., description="工作空间 ID"),
    iteration_note: Optional[str] = Query(None, description="本次迭代备注"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    签入零件版本：
    - 冻结当前草稿迭代（写 check_in_date）
    - 生成下一迭代（iteration + 1）
    - 清签出锁
    - 409 若未签出或非签出本人
    """
    revision = checkin(
        db,
        number=number,
        version=version,
        workspace_id=workspace_id,
        current_user_id=current_user.id,
        iteration_note=iteration_note,
    )
    return CheckoutResponse(
        number=number,
        version=revision.version,
        status=revision.status,
        checkout_user_id=revision.checkout_user_id,
        checkout_date=revision.checkout_date,
        message="签入成功",
    )


@router.put("/{number}/{version}/undocheckout", response_model=CheckoutResponse, summary="撤销签出")
def undocheckout_endpoint(
    number: str,
    version: str,
    workspace_id: uuid.UUID = Query(..., description="工作空间 ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    撤销签出：丢弃未签入的草稿迭代，清签出锁。
    - 409 若未签出或非签出本人
    """
    revision = undocheckout(
        db,
        number=number,
        version=version,
        workspace_id=workspace_id,
        current_user_id=current_user.id,
    )
    return CheckoutResponse(
        number=number,
        version=revision.version,
        status=revision.status,
        checkout_user_id=revision.checkout_user_id,
        checkout_date=revision.checkout_date,
        message="撤销签出成功",
    )


# ---------------------------------------------------------------------------
# 内部辅助：组装含 revisions/iterations 的完整响应
# ---------------------------------------------------------------------------

def _enrich_response(db: Session, master) -> PartResponse:
    """
    把 PartMaster ORM 对象连同其版本/迭代一起组装成 PartResponse。
    手动 eager load，避免 lazy load 在 session 关闭后报错。
    """
    from app.models.part import PartIteration, PartRevision
    from app.schemas.part import IterationResponse, RevisionResponse

    revisions_orm = (
        db.query(PartRevision)
        .filter(
            PartRevision.part_master_id == master.id,
            PartRevision.deleted_at.is_(None),
        )
        .order_by(PartRevision.version)
        .all()
    )
    revisions = []
    for rev in revisions_orm:
        iters_orm = (
            db.query(PartIteration)
            .filter(PartIteration.part_revision_id == rev.id)
            .order_by(PartIteration.iteration)
            .all()
        )
        rev_resp = RevisionResponse.model_validate(rev)
        rev_resp.iterations = [IterationResponse.model_validate(it) for it in iters_orm]
        revisions.append(rev_resp)

    resp = PartResponse.model_validate(master)
    resp.revisions = revisions
    return resp
