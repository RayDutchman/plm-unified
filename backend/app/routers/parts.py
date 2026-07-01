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

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field
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
from app.models.part import PartRevision, PartIteration
from app.routers.auth import get_current_active_user
from app.schemas.part import (
    CheckoutResponse,
    PartCreate,
    PartListItem,
    PartResponse,
    _to_camel,
)

router = APIRouter(prefix="/api/parts", tags=["零件管理"])

# PartRevision.status（大写）→ 前端使用的小写枚举
_PART_STATUS_MAP = {"WIP": "draft", "FROZEN": "frozen", "RELEASED": "released", "OBSOLETE": "obsolete"}


def _latest_version_status(db: Session, part_master_id):
    """取零件最新版本（version 字母倒序第一）的 version 与归一化 status。"""
    from app.models.part import PartRevision
    rev = (
        db.query(PartRevision)
        .filter(PartRevision.part_master_id == part_master_id, PartRevision.deleted_at.is_(None))
        .order_by(PartRevision.version.desc())
        .first()
    )
    if not rev:
        return "", ""
    return rev.version, _PART_STATUS_MAP.get(rev.status, (rev.status or "").lower())


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
    updated_since: float | None = Query(None),
    brief: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    列出工作空间内所有未删除的零件，附最新版本状态。
    updated_since: UNIX 时间戳，增量同步用（包含已删除）。
    brief: 仅返回 id/number/name/updated_at/deleted_at。
    """
    from app.models.part import PartRevision  # 避免循环导入
    masters = list_parts(db, workspace_id=workspace_id, skip=skip, limit=limit, updated_since=updated_since)
    if brief:
        return [{
            "id": str(m.id), "number": m.number, "name": m.name,
            "updated_at": m.updated_at.isoformat() if m.updated_at else None,
            "deleted_at": m.deleted_at.isoformat() if m.deleted_at else None,
        } for m in masters]
    # 一次查询获取所有最新版本，避免 N+1
    master_ids = [m.id for m in masters]
    revisions = db.query(PartRevision).filter(
        PartRevision.part_master_id.in_(master_ids),
        PartRevision.deleted_at.is_(None),
    ).order_by(PartRevision.part_master_id, PartRevision.version.desc()).all()
    # 为每个 master 取最新版本（按 master_id 分组，每组第一个即最新）
    rev_map = {}
    for rev in revisions:
        if rev.part_master_id not in rev_map:
            rev_map[rev.part_master_id] = rev
    result = []
    for m in masters:
        rev = rev_map.get(m.id)
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


class PartUpdateFields(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    type: Optional[str] = Field(None, max_length=50)
    standard_part: Optional[bool] = None

    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True)


@router.put("/{identifier}", response_model=PartResponse, summary="更新零件主数据")
def update_part_endpoint(
    identifier: str,
    data: PartUpdateFields,
    workspace_id: uuid.UUID = Query(..., description="工作空间 ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    uid = uuid.UUID(identifier)
    master = db.query(PartMaster).filter(
        PartMaster.id == uid,
        PartMaster.deleted_at.is_(None),
    ).first()
    if not master:
        raise HTTPException(status_code=404, detail="零部件不存在")
    if data.name is not None:
        master.name = data.name
    if data.type is not None:
        master.type = data.type
    if data.standard_part is not None:
        master.standard_part = data.standard_part
    db.commit()
    db.refresh(master)
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
    from app.models.part import PartIteration, PartRevision
    from app.models.assembly import PartUsageLink
    from app.schemas.part import IterationResponse, RevisionResponse, UsageLinkBriefSchema

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

    if revisions:
        latest_rev = revisions[-1]
        resp.latest_version = latest_rev.version
        resp.latest_status = latest_rev.status
        resp.checkout_user_id = latest_rev.checkout_user_id

    usage_links = (
        db.query(PartUsageLink)
        .join(PartIteration, PartUsageLink.parent_iteration_id == PartIteration.id)
        .join(PartRevision, PartIteration.part_revision_id == PartRevision.id)
        .filter(PartRevision.part_master_id == master.id)
        .order_by(PartUsageLink.order)
        .all()
    )
    if usage_links:
        resp.is_assembly = True
        resp.child_count = len(usage_links)
        ulinks = []
        for link in usage_links:
            child = db.get(PartMaster, link.component_master_id)
            ulinks.append(UsageLinkBriefSchema(
                component_number=child.number if child else "?",
                component_name=child.name if child else "?",
                amount=link.amount,
                unit=link.unit,
            ))
        resp.usage_links = ulinks

    return resp


# ---------------------------------------------------------------------------
# 装配子项管理（PartUsageLink CRUD on PartMaster）
# ---------------------------------------------------------------------------

@router.get("/{identifier}/parts", summary="查询零部件子项清单")
def list_part_children(
    identifier: str,
    workspace_id: uuid.UUID = Query(..., description="工作空间 ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    from app.models.assembly import PartUsageLink
    from app.models.part import PartRevision, PartIteration
    uid = uuid.UUID(identifier)
    master = db.query(PartMaster).filter(PartMaster.id == uid, PartMaster.deleted_at.is_(None)).first()
    if not master:
        raise HTTPException(status_code=404, detail="零部件不存在")
    result = []
    revisions = db.query(PartRevision).filter(
        PartRevision.part_master_id == master.id, PartRevision.deleted_at.is_(None)
    ).order_by(PartRevision.version.desc()).all()
    for rev in revisions:
        iterations = db.query(PartIteration).filter(
            PartIteration.part_revision_id == rev.id
        ).order_by(PartIteration.iteration.desc()).all()
        for it in iterations:
            links = db.query(PartUsageLink).filter(
                PartUsageLink.parent_iteration_id == it.id
            ).order_by(PartUsageLink.order).all()
            for link in links:
                child_master = db.get(PartMaster, link.component_master_id)
                c_version, c_status = _latest_version_status(db, link.component_master_id) if child_master else ("", "")
                result.append({
                    "id": str(link.id),
                    "childType": "part" if not _has_children(db, link.component_master_id) else "component",
                    "child_id": str(link.component_master_id),
                    "quantity": link.amount,
                    "unit": link.unit,
                    "child_detail": {
                        "id": str(child_master.id) if child_master else "",
                        "code": child_master.number if child_master else "?",
                        "name": child_master.name if child_master else "?",
                        "spec": child_master.type or "",
                        "version": c_version,
                        "status": c_status,
                    } if child_master else None,
                    "created_at": "",
                })
    return result


def _has_children(db: Session, master_id: uuid.UUID) -> bool:
    from app.models.assembly import PartUsageLink
    revisions = db.query(PartRevision).filter(PartRevision.part_master_id == master_id, PartRevision.deleted_at.is_(None)).all()
    for rev in revisions:
        iterations = db.query(PartIteration).filter(PartIteration.part_revision_id == rev.id).all()
        for it in iterations:
            if db.query(PartUsageLink).filter(PartUsageLink.parent_iteration_id == it.id).first():
                return True
    return False


class AddPartChildBody(BaseModel):
    child_type: str = "part"
    child_id: str
    quantity: float = 1.0

    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True)


class UpdatePartChildBody(BaseModel):
    quantity: float

    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True)


@router.post("/{identifier}/parts", summary="添加子项")
def add_part_child(
    identifier: str,
    data: AddPartChildBody,
    workspace_id: uuid.UUID = Query(..., description="工作空间 ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    from app.models.assembly import PartUsageLink
    uid = uuid.UUID(identifier)
    master = db.query(PartMaster).filter(PartMaster.id == uid, PartMaster.deleted_at.is_(None)).first()
    if not master:
        raise HTTPException(status_code=404, detail="零部件不存在")
    child = db.query(PartMaster).filter(PartMaster.id == uuid.UUID(data.child_id), PartMaster.deleted_at.is_(None)).first()
    if not child:
        raise HTTPException(status_code=404, detail="子零部件不存在")
    latest_rev = db.query(PartRevision).filter(
        PartRevision.part_master_id == master.id, PartRevision.deleted_at.is_(None)
    ).order_by(PartRevision.version.desc()).first()
    if not latest_rev:
        raise HTTPException(status_code=400, detail="零部件没有版本记录")
    it = db.query(PartIteration).filter(
        PartIteration.part_revision_id == latest_rev.id
    ).order_by(PartIteration.iteration.desc()).first()
    if not it:
        raise HTTPException(status_code=400, detail="没有可用迭代")
    link = PartUsageLink(
        id=uuid.uuid4(),
        parent_iteration_id=it.id,
        component_master_id=child.id,
        amount=data.quantity,
    )
    db.add(link)
    db.commit()
    return {"id": str(link.id), "message": "子项已添加"}


@router.put("/{identifier}/parts/{item_id}", summary="更新子项用量")
def update_part_child(
    identifier: str,
    item_id: str,
    data: UpdatePartChildBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    from app.models.assembly import PartUsageLink
    link = db.query(PartUsageLink).filter(PartUsageLink.id == uuid.UUID(item_id)).first()
    if not link:
        raise HTTPException(status_code=404, detail="子项不存在")
    link.amount = data.quantity
    db.commit()
    return {"message": "用量已更新"}


@router.delete("/{identifier}/parts/{item_id}", summary="移除子项")
def remove_part_child(
    identifier: str,
    item_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    from app.models.assembly import PartUsageLink
    link = db.query(PartUsageLink).filter(PartUsageLink.id == uuid.UUID(item_id)).first()
    if not link:
        raise HTTPException(status_code=404, detail="子项不存在")
    db.delete(link)
    db.commit()
    return {"message": "子项已移除"}


@router.get("/{identifier}/parents", summary="查询零部件所有上级父项")
def get_part_parents(
    identifier: str,
    workspace_id: uuid.UUID = Query(..., description="工作空间 ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    from app.models.assembly import PartUsageLink
    uid = uuid.UUID(identifier)
    master = db.query(PartMaster).filter(PartMaster.id == uid, PartMaster.deleted_at.is_(None)).first()
    if not master:
        raise HTTPException(status_code=404, detail="零部件不存在")

    ancestors = set()
    visited = set()
    queue = [uid]

    while queue:
        current = queue.pop(0)
        if current in visited:
            continue
        visited.add(current)
        links = db.query(PartUsageLink).filter(
            PartUsageLink.component_master_id == current
        ).all()
        for link in links:
            it = db.get(PartIteration, link.parent_iteration_id)
            if not it:
                continue
            rev = db.get(PartRevision, it.part_revision_id)
            if not rev or rev.deleted_at is not None:
                continue
            pm = db.get(PartMaster, rev.part_master_id)
            if pm and pm.id not in ancestors:
                ancestors.add(pm.id)
                queue.append(pm.id)

    return [{"id": str(a), "number": "", "name": ""} for a in ancestors]
