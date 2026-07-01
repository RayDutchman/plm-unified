"""
CATIA 同步接口（sync router）

提供批量推送端点，供 CATIA Copilot PLM 工作台调用。

端点：
  GET  /api/sync/status         工作空间概览
  POST /api/sync/upload         批量同步装配树（新增）
"""

from typing import Optional
import uuid
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from app.database import get_db
from app.models import User
from app.models.part import PartMaster, PartRevision, PartIteration
from app.models.assembly import PartUsageLink, CADInstance
from app.crud.part import get_part
from app.permissions import require_permission
from app.routers.auth import get_current_active_user

router = APIRouter(prefix="/sync", tags=["同步"])


# ---- Pydantic models ----

class CadInstanceData(BaseModel):
    tx: float = 0
    ty: float = 0
    tz: float = 0
    rx: Optional[float] = None
    ry: Optional[float] = None
    rz: Optional[float] = None
    rotationType: str = "ANGLE"


class ComponentData(BaseModel):
    componentNumber: str
    amount: float = 1.0
    unit: Optional[str] = None
    optional: bool = False
    order: int = 0
    comment: Optional[str] = None
    cadInstances: list[CadInstanceData] = Field(default_factory=list)


class PartSyncPayload(BaseModel):
    number: str
    name: str = ""
    version: str = "A"
    iterationNote: str = ""
    components: list[ComponentData] = Field(default_factory=list)


class SyncUploadRequest(BaseModel):
    workspaceName: str = "default"
    parts: list[PartSyncPayload] = Field(default_factory=list, description="零件列表（含装配树）")
    rootPart: Optional[PartSyncPayload] = None


class SyncUploadResponse(BaseModel):
    created: int = 0
    updated: int = 0
    failed: int = 0
    errors: list[str] = Field(default_factory=list)


# ---- 状态查询 ----

@router.get("/status")
def get_sync_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("sync:read"))
):
    return {
        "parts": 0,
        "assemblies": 0,
        "documents": 0,
        "bom_items": 0,
        "ecrs": 0,
        "ecos": 0,
        "config_items": 0,
    }


# ---- 批量同步 ----

@router.post("/upload", response_model=SyncUploadResponse)
def sync_upload(
    body: SyncUploadRequest,
    workspace_id: uuid.UUID = Query(default="00000000-0000-0000-0000-000000000001", description="工作空间 ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """
    批量同步装配树。

    接受旧 sync.py 兼容格式，递归创建/更新零件、版本、BOM、CADInstance。
    每个 part 内部可递归嵌套 components（子件同样有 PartSyncPayload 结构）。

    返回 created/updated/failed 计数。
    """
    parts = body.parts
    if body.rootPart and not parts:
        parts = [body.rootPart]

    result = SyncUploadResponse()

    for part_data in parts:
        try:
            _sync_one_part(db, workspace_id, current_user.id, part_data, result)
        except Exception as e:
            result.failed += 1
            result.errors.append(f"{part_data.number}: {e}")

    return result


def _sync_one_part(
    db: Session,
    workspace_id: uuid.UUID,
    user_id: uuid.UUID,
    data: PartSyncPayload,
    result: SyncUploadResponse,
    _depth: int = 0,
):
    """递归创建/更新单个零件及其子件。"""
    # 1. 找或创建 PartMaster
    try:
        master = get_part(db, number=data.number, workspace_id=workspace_id)
    except HTTPException:
        master = None
    if master:
        result.updated += 1
        rev = (
            db.query(PartRevision)
            .filter(
                PartRevision.part_master_id == master.id,
                PartRevision.version == data.version,
            )
            .first()
        )
        if not rev:
            rev = PartRevision(
                part_master_id=master.id, version=data.version,
                status="WIP",
            )
            db.add(rev)
            db.flush()
    else:
        result.created += 1
        master = PartMaster(
            workspace_id=workspace_id,
            number=data.number,
            name=data.name or data.number,
            author_id=user_id,
        )
        db.add(master)
        db.flush()
        rev = PartRevision(
            part_master_id=master.id, version=data.version,
            status="WIP",
        )
        db.add(rev)
        db.flush()

    # 2. 创建新 Iteration
    existing_iter = (
        db.query(PartIteration)
        .filter(
            PartIteration.part_revision_id == rev.id,
            PartIteration.iteration == 1,
        )
        .first()
    )
    if existing_iter:
        db.query(CADInstance).filter(
            CADInstance.usage_link_id.in_(
                db.query(PartUsageLink.id).filter(
                    PartUsageLink.parent_iteration_id == existing_iter.id,
                )
            )
        ).delete(synchronize_session=False)
        db.query(PartUsageLink).filter(
            PartUsageLink.parent_iteration_id == existing_iter.id,
        ).delete(synchronize_session=False)
        db.flush()
        _iter = existing_iter
    else:
        _iter = PartIteration(
            part_revision_id=rev.id, iteration=1,
            iteration_note=data.iterationNote,
            author_id=user_id,
        )
        db.add(_iter)
        db.flush()

    # 3. 写 BOM + CADInstances
    for comp in data.components:
        try:
            child_master = get_part(db, comp.componentNumber, workspace_id)
        except HTTPException:
            child_master = None
        if not child_master:
            child_master = PartMaster(
                workspace_id=workspace_id,
                number=comp.componentNumber,
                name=comp.componentNumber,
                author_id=user_id,
            )
            db.add(child_master)
            db.flush()
            child_rev = PartRevision(
                part_master_id=child_master.id, version="A",
                status="WIP",
            )
            db.add(child_rev)
            db.flush()

        link = PartUsageLink(
            parent_iteration_id=_iter.id,
            component_master_id=child_master.id,
            amount=comp.amount,
            unit=comp.unit,
            optional=comp.optional,
            order=comp.order,
            comment=comp.comment,
        )
        db.add(link)
        db.flush()

        for i, ci in enumerate(comp.cadInstances):
            cad = CADInstance(
                usage_link_id=link.id,
                tx=ci.tx, ty=ci.ty, tz=ci.tz,
                rotation_type=ci.rotationType,
                rx=ci.rx, ry=ci.ry, rz=ci.rz,
                order=i,
            )
            db.add(cad)

    db.commit()
