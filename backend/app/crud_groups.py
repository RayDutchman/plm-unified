"""用户组查询与图文档内容访问判定助手。"""
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.models_document import DocumentGroupLink, Document, DocumentAttachment
from app.models.user_groups import user_group_members as ugm_table


def get_user_group_ids(db: Session, user_id) -> set:
    rows = db.query(ugm_table.c.group_id).filter(ugm_table.c.user_id == user_id).all()
    return {r[0] for r in rows}


def get_document_group_ids(db: Session, document_id) -> set:
    rows = db.query(DocumentGroupLink.group_id).filter(DocumentGroupLink.document_id == document_id).all()
    return {r[0] for r in rows}


def _document_content_accessible(user_group_ids: set, doc_group_ids: set) -> bool:
    if not doc_group_ids:
        return True
    return bool(user_group_ids & doc_group_ids)


def document_is_accessible(db: Session, user, document) -> bool:
    return _document_content_accessible(
        get_user_group_ids(db, user.id),
        get_document_group_ids(db, document.id),
    )


def enforce_document_content_access(db: Session, user, document) -> None:
    if not document_is_accessible(db, user, document):
        raise HTTPException(status_code=403, detail="无权访问该图文档内容")


def enforce_attachment_content_access(db: Session, user, attachment_id) -> None:
    att = db.query(DocumentAttachment).filter(DocumentAttachment.id == attachment_id).first()
    if not att or not att.document_id:
        return
    document = db.query(Document).filter(Document.id == att.document_id).first()
    if not document:
        return
    enforce_document_content_access(db, user, document)
