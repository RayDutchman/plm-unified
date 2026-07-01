"""零部件附件/文档链接路由（PartMaster）。"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.models.part import PartMaster
from app.models.pdm import PartAttachment
from app.models.models_document import Document
from app.routers.auth import get_current_active_user
from app.core.permissions import require_permission

router = APIRouter(prefix="/api/components", tags=["零部件附件/文档"])


class LinkDocumentBody(BaseModel):
    document_id: uuid.UUID
    category: Optional[str] = None
    sort_order: int = 0


class UpdateLinkDocumentBody(BaseModel):
    category: Optional[str] = None
    sort_order: Optional[int] = None


def _get_part_master(db: Session, part_master_id: uuid.UUID) -> PartMaster:
    pm = db.query(PartMaster).filter(
        PartMaster.id == part_master_id,
        PartMaster.deleted_at.is_(None),
    ).first()
    if not pm:
        raise HTTPException(status_code=404, detail="零部件不存在")
    return pm


# ── 附件 ──────────────────────────────────────────────────────────────

@router.get("/{part_master_id}/attachments")
def list_attachments(
    part_master_id: uuid.UUID,
    category: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    _get_part_master(db, part_master_id)
    q = db.query(PartAttachment).filter(
        PartAttachment.part_master_id == part_master_id,
    )
    if category:
        q = q.filter(PartAttachment.category == category)
    return q.order_by(PartAttachment.created_at.desc()).all()


@router.delete("/{part_master_id}/attachments/{attachment_id}")
def delete_attachment(
    part_master_id: uuid.UUID,
    attachment_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("components:manage")),
):
    _get_part_master(db, part_master_id)
    att = db.query(PartAttachment).filter(
        PartAttachment.id == attachment_id,
        PartAttachment.part_master_id == part_master_id,
    ).first()
    if not att:
        raise HTTPException(status_code=404, detail="附件不存在")
    db.delete(att)
    db.commit()
    return {"message": "附件已删除"}


# ── 文档链接 ──────────────────────────────────────────────────────────

def _enrich_links(links: list, db: Session) -> list:
    doc_ids = {link.get("document_id") for link in links if link.get("document_id")}
    if not doc_ids:
        return links
    docs = db.query(Document).filter(
        Document.id.in_(list(doc_ids)),
        Document.deleted_at.is_(None),
    ).all()
    doc_map = {str(d.id): d for d in docs}
    result = []
    for link in links:
        entry = dict(link)
        did = str(link.get("document_id", ""))
        doc = doc_map.get(did)
        if doc:
            entry["document"] = {
                "id": str(doc.id),
                "code": doc.code,
                "name": doc.name,
                "version": doc.version,
                "status": doc.status,
                "file_name": doc.file_name,
                "file_id": str(doc.file_id) if doc.file_id else None,
            }
            result.append(entry)
    return result


@router.get("/{component_id}/documents")
def list_document_links(
    component_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    comp = _get_part_master(db, component_id)
    links = comp.document_links or []
    return _enrich_links(links, db)


@router.post("/{component_id}/documents")
def link_document(
    component_id: uuid.UUID,
    body: LinkDocumentBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("components.doc:link")),
):
    comp = _get_part_master(db, component_id)
    doc = db.query(Document).filter(
        Document.id == body.document_id,
        Document.deleted_at.is_(None),
    ).first()
    if not doc:
        raise HTTPException(status_code=404, detail="文档不存在")
    links = list(comp.document_links or [])
    link_id = str(uuid.uuid4())
    new_link = {
        "id": link_id,
        "document_id": str(body.document_id),
        "category": body.category,
        "sort_order": body.sort_order,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    links.append(new_link)
    comp.document_links = links
    db.commit()
    db.refresh(comp)
    return _enrich_links([new_link], db)[0]


@router.put("/{component_id}/documents/{link_id}")
def update_document_link(
    component_id: uuid.UUID,
    link_id: str,
    body: UpdateLinkDocumentBody,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("components.doc:link")),
):
    comp = _get_part_master(db, component_id)
    links = list(comp.document_links or [])
    updated = None
    for link in links:
        if link.get("id") == link_id:
            if body.category is not None:
                link["category"] = body.category
            if body.sort_order is not None:
                link["sort_order"] = body.sort_order
            updated = link
            break
    if updated is None:
        raise HTTPException(status_code=404, detail="文档链接不存在")
    comp.document_links = links
    db.commit()
    return _enrich_links([updated], db)[0]


@router.delete("/{component_id}/documents/{link_id}")
def unlink_document(
    component_id: uuid.UUID,
    link_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("components.doc:unlink")),
):
    comp = _get_part_master(db, component_id)
    links = list(comp.document_links or [])
    new_links = [link for link in links if link.get("id") != link_id]
    if len(new_links) == len(links):
        raise HTTPException(status_code=404, detail="文档链接不存在")
    comp.document_links = new_links
    db.commit()
    return {"message": "文档链接已移除"}
