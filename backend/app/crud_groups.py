"""用户组查询与图文档内容访问判定助手。"""
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.models_document import DocumentGroupLink, Document, DocumentAttachment
from app.models.user_groups import user_group_members as ugm_table
from app.permissions import check_object_policy, enforce_object_policy


def get_user_group_ids(db: Session, user_id) -> set:
    rows = db.query(ugm_table.c.group_id).filter(ugm_table.c.user_id == user_id).all()
    return {r[0] for r in rows}


def get_document_group_ids(db: Session, document_id) -> set:
    rows = db.query(DocumentGroupLink.group_id).filter(DocumentGroupLink.document_id == document_id).all()
    return {r[0] for r in rows}


def document_is_accessible(db: Session, user, document) -> bool:
    return check_object_policy(
        "document_content_access", user, document,
        user_group_ids=get_user_group_ids(db, user.id),
        doc_group_ids=get_document_group_ids(db, document.id),
    )


def enforce_document_content_access(db: Session, user, document) -> None:
    enforce_object_policy(
        "document_content_access", user, document,
        user_group_ids=get_user_group_ids(db, user.id),
        doc_group_ids=get_document_group_ids(db, document.id),
    )


def enforce_attachment_content_access(db: Session, user, attachment_id) -> None:
    att = db.query(DocumentAttachment).filter(DocumentAttachment.id == attachment_id).first()
    if not att or not att.document_id:
        return
    document = db.query(Document).filter(Document.id == att.document_id).first()
    if not document:
        return
    enforce_document_content_access(db, user, document)
