"""BOM 路由（适配 part_usage_links + cad_instances）。"""
from __future__ import annotations
import csv
import io
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.models.assembly import PartUsageLink, CADInstance
from app.models.part import PartMaster, PartRevision, PartIteration
from app.routers.auth import get_current_active_user

router = APIRouter(prefix="/bom", tags=["BOM"])


@router.get("/items/all")
def get_all_bom_items(
    workspace_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    links = (
        db.query(PartUsageLink)
        .join(PartIteration, PartUsageLink.parent_iteration_id == PartIteration.id)
        .join(PartRevision, PartIteration.part_revision_id == PartRevision.id)
        .join(PartMaster, PartRevision.part_master_id == PartMaster.id)
        .filter(PartMaster.workspace_id == workspace_id, PartMaster.deleted_at.is_(None))
        .all()
    )
    result = []
    for link in links:
        child = db.get(PartMaster, link.component_master_id)
        result.append({
            "id": str(link.id),
            "parentType": "part",
            "parentId": str(link.parent_iteration_id),
            "childType": "part",
            "childId": str(link.component_master_id),
            "childCode": child.number if child else "?",
            "childName": child.name if child else "?",
            "quantity": link.amount,
            "unit": link.unit,
            "order": link.order,
            "optional": link.optional,
        })
    return result


def _build_bom_tree(db: Session, master: PartMaster, visited: set | None = None) -> dict:
    if visited is None:
        visited = set()
    key = str(master.id)
    if key in visited:
        return {"id": key, "code": master.number, "name": master.name, "children": [], "_circular": True}
    visited.add(key)

    revision = (
        db.query(PartRevision)
        .filter(PartRevision.part_master_id == master.id, PartRevision.deleted_at.is_(None))
        .order_by(PartRevision.version.desc())
        .first()
    )
    if not revision:
        return {"id": key, "code": master.number, "name": master.name, "children": []}

    iteration = (
        db.query(PartIteration)
        .filter(PartIteration.part_revision_id == revision.id, PartIteration.check_in_date.is_not(None))
        .order_by(PartIteration.iteration.desc())
        .first()
    )
    if not iteration:
        return {"id": key, "code": master.number, "name": master.name, "children": []}

    links = (
        db.query(PartUsageLink)
        .filter(PartUsageLink.parent_iteration_id == iteration.id)
        .order_by(PartUsageLink.order)
        .all()
    )

    children = []
    for link in links:
        child_master = db.get(PartMaster, link.component_master_id)
        if child_master:
            child_tree = _build_bom_tree(db, child_master, visited.copy())
            child_tree["quantity"] = link.amount
            child_tree["unit"] = link.unit
            child_tree["order"] = link.order
            children.append(child_tree)

    return {"id": key, "code": master.number, "name": master.name, "children": children}


@router.get("/tree/{entity_type}/{entity_id}")
def get_bom_tree(
    entity_type: str,
    entity_id: str,
    workspace_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    root_master = db.get(PartMaster, uuid.UUID(entity_id))
    if not root_master:
        raise HTTPException(status_code=404, detail="零件不存在")
    return _build_bom_tree(db, root_master)


@router.get("/trace/{entity_type}/{entity_id}")
def trace_where_used(
    entity_type: str,
    entity_id: str,
    workspace_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    component_id = uuid.UUID(entity_id)
    links = db.query(PartUsageLink).filter(PartUsageLink.component_master_id == component_id).all()
    result = []
    for link in links:
        iteration = db.get(PartIteration, link.parent_iteration_id)
        if not iteration:
            continue
        revision = db.get(PartRevision, iteration.part_revision_id)
        if not revision:
            continue
        parent_master = db.get(PartMaster, revision.part_master_id)
        if not parent_master:
            continue
        result.append({
            "parentCode": parent_master.number,
            "parentName": parent_master.name,
            "parentVersion": revision.version,
            "quantity": link.amount,
        })
    return result


@router.get("/references/{entity_type}/{entity_id}")
def get_references(
    entity_type: str,
    entity_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    eid = uuid.UUID(entity_id)
    links = db.query(PartUsageLink).filter(PartUsageLink.component_master_id == eid).all()
    result = []
    for link in links:
        iteration = db.get(PartIteration, link.parent_iteration_id)
        if not iteration:
            continue
        revision = db.get(PartRevision, iteration.part_revision_id)
        if not revision:
            continue
        parent_master = db.get(PartMaster, revision.part_master_id)
        if not parent_master:
            continue
        result.append({
            "parentType": "part",
            "parentId": str(parent_master.id),
            "parentCode": parent_master.number,
            "parentName": parent_master.name,
        })
    return result


@router.get("/export/{entity_type}/{entity_id}")
def export_bom_csv(
    entity_type: str,
    entity_id: str,
    workspace_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    master = db.get(PartMaster, uuid.UUID(entity_id))
    if not master:
        raise HTTPException(status_code=404, detail="零件不存在")
    tree = _build_bom_tree(db, master)

    def _flatten(node, level=0):
        rows = []
        rows.append([node.get("code", ""), node.get("name", ""), str(level), str(node.get("quantity", "")), node.get("unit", "")])
        for child in node.get("children", []):
            rows.extend(_flatten(child, level + 1))
        return rows

    rows = _flatten(tree)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["编号", "名称", "层级", "数量", "单位"])
    writer.writerows(rows)
    output.seek(0)
    content = output.getvalue().encode("utf-8-sig")
    return StreamingResponse(
        io.BytesIO(content),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={master.number}_BOM.csv"},
    )
