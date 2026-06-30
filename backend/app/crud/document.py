"""图文档 CRUD 辅助函数。"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.models_document import Document, DocumentLink
from app.models.part import PartMaster


def create_log(
    db: Session,
    user_id: uuid.UUID,
    username: str,
    action: str,
    target_type: str | None = None,
    target_id: str | None = None,
    detail: str | None = None,
    ip_address: str | None = None,
    id: uuid.UUID | None = None,
):
    pass


def _get_next_version(db: Session, model, code: str) -> str:
    """获取下一个版本号：A → B → C … Z → AA"""
    latest = (
        db.query(model)
        .filter(model.code == code, model.deleted_at.is_(None))
        .order_by(model.version.desc())
        .first()
    )
    if not latest:
        return "A"
    v = latest.version
    if not v:
        return "A"
    if v.isalpha() and v.isupper():
        if v == "Z":
            return "AA"
        last = v[-1]
        if last == "Z":
            return chr(ord(v[0]) + 1) + "A"
        return v[:-1] + chr(ord(last) + 1)
    return "A"


def upgrade_document(db: Session, doc_id: uuid.UUID, user: str | None = None):
    source = db.query(Document).filter(Document.id == doc_id).first()
    if not source:
        return None, "图文档不存在"
    if source.status not in ("released", "obsolete"):
        return None, "仅发布或作废状态的图文档允许升版"

    new_version = _get_next_version(db, Document, source.code)
    new_doc = Document(
        code=source.code,
        name=source.name,
        version=new_version,
        status="draft",
        remark=source.remark,
        creator_id=source.creator_id,
    )
    db.add(new_doc)
    db.commit()
    db.refresh(new_doc)
    return new_doc, None


def get_document_versions(db: Session, doc_id: uuid.UUID) -> list[Document]:
    doc = db.query(Document).filter(Document.id == doc_id).first()
    if not doc:
        return []
    return (
        db.query(Document)
        .filter(Document.code == doc.code)
        .order_by(Document.created_at)
        .all()
    )


def find_doc_refs(db: Session, doc_id: uuid.UUID) -> list[dict]:
    """通过 document_links 独立表查找引用该图文档的实体。"""
    links = (
        db.query(DocumentLink)
        .filter(DocumentLink.document_id == doc_id)
        .all()
    )
    references = []
    for link in links:
        entity_code = ""
        entity_name = ""
        version = ""
        status = ""
        if link.entity_type == "part_master":
            master = db.query(PartMaster).filter(PartMaster.id == link.entity_id).first()
            if master:
                entity_code = master.number
                entity_name = master.name
        references.append(
            {
                "entity_type": link.entity_type,
                "entity_id": str(link.entity_id),
                "entity_code": entity_code,
                "entity_name": entity_name,
                "version": version,
                "status": status,
                "id": str(link.entity_id),
                "code": entity_code,
                "name": entity_name,
            }
        )
    return references
