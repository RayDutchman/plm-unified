"""图文档路由 — 从 myPDM 迁移并适配。"""
from __future__ import annotations

import base64
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import get_db
from app.models.user import User as UserModel
from app.models.user_groups import UserGroup
from app.models.models_document import Document, DocumentAttachment, DocumentLink, DocumentGroupLink
from app.models.part import PartMaster
from app.routers.auth import get_current_active_user
from app.permissions import require_permission
from app.schemas.document import DocumentCreate, DocumentUpdate, DocumentAttachmentCreate, UpgradeRequest
from app.crud_groups import get_user_group_ids, get_document_group_ids, document_is_accessible, enforce_document_content_access
from app.stp_converter import is_stp_file, delete_glb_cache
from app.office_converter import is_office_file, delete_pdf_cache
from app.crud.document import create_log, upgrade_document, get_document_versions, find_doc_refs

router = APIRouter(prefix="/documents", tags=["图文档管理"])


def _resolve_group_names(db: Session, gids: set) -> list:
    if not gids:
        return []
    gs = db.query(UserGroup).filter(UserGroup.id.in_(gids)).all()
    gname_map = {g.id: g.name for g in gs}
    return [gname_map.get(gid, str(gid)) for gid in gids]


def _check_accessible(user, doc, user_group_ids: set, doc_groups: set) -> bool:
    if user.role == "admin":
        return True
    if getattr(doc, "creator_id", None) == user.id:
        return True
    if not doc_groups:
        return True
    return bool(user_group_ids & doc_groups)


@router.get("/")
async def list_documents(
    skip: int = 0,
    limit: int = 100,
    keyword: Optional[str] = None,
    status: Optional[str] = None,
    updated_since: Optional[float] = None,
    brief: bool = False,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_permission("documents:read")),
):
    query = db.query(Document)
    if not updated_since:
        query = query.filter(Document.deleted_at.is_(None))
    if keyword:
        kw = f"%{keyword.strip().lower()}%"
        query = query.filter(
            (Document.code.ilike(kw)) | (Document.name.ilike(kw))
        )
    if status:
        query = query.filter(Document.status == status)
    if updated_since:
        since_dt = datetime.fromtimestamp(updated_since, tz=timezone.utc)
        query = query.filter(
            (Document.updated_at >= since_dt)
            | (Document.deleted_at >= since_dt)
        )
    docs = query.offset(skip).limit(limit).all()

    user_group_ids = get_user_group_ids(db, current_user.id)
    doc_ids = [d.id for d in docs]
    links = (
        db.query(DocumentGroupLink)
        .filter(DocumentGroupLink.document_id.in_(doc_ids))
        .all()
    ) if doc_ids else []
    doc_groups = {}
    for lk in links:
        doc_groups.setdefault(lk.document_id, set()).add(lk.group_id)

    creator_ids = {d.creator_id for d in docs if d.creator_id}
    creator_map = {}
    if creator_ids:
        users = db.query(UserModel).filter(UserModel.id.in_(creator_ids)).all()
        creator_map = {u.id: u.real_name for u in users}

    all_gids: set = set()
    for gids in doc_groups.values():
        all_gids.update(gids)
    group_name_map = {}
    if all_gids:
        gs = db.query(UserGroup).filter(UserGroup.id.in_(all_gids)).all()
        group_name_map = {g.id: g.name for g in gs}

    def _accessible(d):
        return _check_accessible(
            current_user, d,
            user_group_ids=user_group_ids,
            doc_groups=doc_groups.get(d.id, set()),
        )

    if brief:
        return JSONResponse(content=[{
            "id": str(d.id), "code": d.code, "name": d.name,
            "version": d.version, "status": d.status, "file_name": d.file_name,
            "file_id": str(d.file_id) if d.file_id else None,
            "remark": d.remark,
            "accessible": _accessible(d),
            "group_ids": [str(g) for g in doc_groups.get(d.id, set())],
            "group_names": [group_name_map.get(g, str(g)) for g in doc_groups.get(d.id, set())],
            "creator_id": str(d.creator_id) if d.creator_id else None,
            "creator_name": creator_map.get(d.creator_id, "") if d.creator_id else "",
            "created_at": d.created_at.isoformat() if d.created_at else None,
            "updated_at": d.updated_at.isoformat() if d.updated_at else None,
            "deleted_at": d.deleted_at.isoformat() if d.deleted_at else None,
        } for d in docs])
    return [{
        "id": d.id, "code": d.code, "name": d.name,
        "version": d.version, "status": d.status,
        "remark": d.remark,
        "file_name": d.file_name, "file_id": d.file_id,
        "creator_id": d.creator_id,
        "creator_name": creator_map.get(d.creator_id, "") if d.creator_id else "",
        "accessible": _accessible(d),
        "group_ids": list(doc_groups.get(d.id, set())),
        "group_names": [group_name_map.get(g, str(g)) for g in doc_groups.get(d.id, set())],
        "created_at": d.created_at, "updated_at": d.updated_at,
        "deleted_at": d.deleted_at,
    } for d in docs]


@router.get("/{doc_id}/references")
async def get_document_references(
    doc_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_permission("documents:read_refs")),
):
    """获取图文档的引用信息（通过 document_links 独立表）"""
    refs = find_doc_refs(db, doc_id)
    return {
        "document_id": str(doc_id),
        "reference_count": len(refs),
        "references": refs,
        "dashboard_folder_count": 0,
        "dashboard_folders": [],
    }


@router.post("/")
async def create_document(
    doc: DocumentCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_permission("documents:create")),
):
    existing = db.query(Document).filter(
        Document.code == doc.code,
        Document.version == "A",
        Document.deleted_at.is_(None),
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="该编号和版本的组合已存在")
    data = doc.model_dump()
    group_ids = data.pop("group_ids", None) or []
    d = Document(**data, creator_id=current_user.id)
    db.add(d)
    db.commit()
    db.refresh(d)
    for gid in set(group_ids):
        db.add(DocumentGroupLink(document_id=d.id, group_id=gid))
    if group_ids:
        db.commit()
    ip = request.client.host if request.client else None
    create_log(db, current_user.id, current_user.username, "创建图文档", "document", str(d.id), f"编号:{d.code}", ip)
    return {
        "id": d.id, "code": d.code, "name": d.name,
        "version": d.version, "status": d.status,
        "remark": d.remark,
        "file_name": d.file_name, "file_id": d.file_id,
        "creator_id": d.creator_id,
        "creator_name": current_user.real_name,
        "group_ids": list(set(group_ids)),
        "created_at": d.created_at, "updated_at": d.updated_at,
    }


@router.get("/{doc_id}")
async def get_document(
    doc_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_permission("documents:read")),
):
    d = db.query(Document).filter(Document.id == doc_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="图文档不存在")
    enforce_document_content_access(db, current_user, d)
    creator_name = ""
    if d.creator_id:
        creator = db.query(UserModel).filter(UserModel.id == d.creator_id).first()
        creator_name = creator.real_name if creator else ""
    gids = get_document_group_ids(db, d.id)
    return {
        "id": d.id, "code": d.code, "name": d.name,
        "version": d.version, "status": d.status,
        "remark": d.remark,
        "file_name": d.file_name, "file_id": d.file_id,
        "creator_id": d.creator_id,
        "creator_name": creator_name,
        "accessible": document_is_accessible(db, current_user, d),
        "group_ids": list(gids),
        "group_names": _resolve_group_names(db, gids),
        "created_at": d.created_at, "updated_at": d.updated_at,
    }


@router.put("/{doc_id}")
async def update_document(
    doc_id: uuid.UUID,
    body: DocumentUpdate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_permission("documents:update")),
):
    d = db.query(Document).filter(Document.id == doc_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="图文档不存在")
    if body.code and body.code != d.code:
        if d.version != "A":
            raise HTTPException(status_code=400, detail="仅 A 版允许修改编号，升版后的版本不可修改编号")
        existing = db.query(Document).filter(
            Document.code == body.code,
            Document.version == d.version,
            Document.deleted_at.is_(None),
            Document.id != doc_id,
        ).first()
        if existing:
            raise HTTPException(status_code=400, detail="该编号和版本的组合已存在")
    update_data = body.model_dump(exclude_unset=True)
    group_ids = update_data.pop("group_ids", None)
    if group_ids is not None:
        db.query(DocumentGroupLink).filter(DocumentGroupLink.document_id == doc_id).delete()
        for gid in set(group_ids):
            db.add(DocumentGroupLink(document_id=doc_id, group_id=gid))
    for field, value in update_data.items():
        setattr(d, field, value)
    db.commit()
    db.refresh(d)
    ip = request.client.host if request.client else None
    create_log(db, current_user.id, current_user.username, "更新图文档", "document", str(doc_id), None, ip)
    creator_name = ""
    if d.creator_id:
        c = db.query(UserModel).filter(UserModel.id == d.creator_id).first()
        creator_name = c.real_name if c else ""
    return {
        "id": d.id, "code": d.code, "name": d.name,
        "version": d.version, "status": d.status,
        "remark": d.remark,
        "file_name": d.file_name, "file_id": d.file_id,
        "creator_id": d.creator_id,
        "creator_name": creator_name,
        "group_ids": list(get_document_group_ids(db, d.id)),
        "created_at": d.created_at, "updated_at": d.updated_at,
    }


@router.get("/{doc_id}/can-delete")
async def check_document_can_delete(
    doc_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_permission("documents:read")),
):
    """检查图文档是否可以被删除（通过 document_links 独立表）"""
    d = db.query(Document).filter(Document.id == doc_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="图文档不存在")
    refs = find_doc_refs(db, doc_id)
    return {
        "can_delete": len(refs) == 0,
        "ref_count": len(refs),
        "references": refs,
    }


@router.delete("/{doc_id}")
async def delete_document(
    doc_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_permission("documents:delete")),
):
    refs = find_doc_refs(db, doc_id)
    if refs:
        labels = [f"{'零件' if r['entity_type'] == 'part_master' else r['entity_type']} {r['code']}" for r in refs[:5]]
        raise HTTPException(
            status_code=400,
            detail=f"该图文档被 {len(refs)} 个实体引用: {', '.join(labels)}，无法删除",
        )
    d = db.query(Document).filter(Document.id == doc_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="图文档不存在")

    from app.file_storage import file_storage
    attachments = db.query(DocumentAttachment).filter(DocumentAttachment.document_id == doc_id).all()
    for att in attachments:
        if hasattr(att, "file_path") and att.file_path:
            try:
                file_storage.delete_file(att.file_path)
                if is_stp_file(att.file_name):
                    delete_glb_cache(str(att.id))
            except Exception as e:
                print(f"[WARNING] Failed to delete file {att.file_path}: {e}")

    db.query(DocumentAttachment).filter(DocumentAttachment.document_id == doc_id).delete()
    d.deleted_at = func.now()
    db.commit()
    ip = request.client.host if request.client else None
    create_log(db, current_user.id, current_user.username, "软删除图文档", "document", str(doc_id), f"编号:{d.code}", ip)
    return {"message": "图文档已软删除"}


@router.post("/{doc_id}/attachments")
async def upload_document_attachment(
    doc_id: uuid.UUID,
    body: DocumentAttachmentCreate,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_permission("documents.attachment:upload")),
):
    from app.file_storage import file_storage

    d = db.query(Document).filter(Document.id == doc_id).first()
    if not d:
        raise HTTPException(status_code=404, detail="图文档不存在")

    try:
        file_data_bytes = base64.b64decode(body.file_data)
        folder_name = f"{d.code}_{d.version}"
        result = file_storage.save_file(
            file_data_bytes, "document", str(doc_id), body.file_name, folder_name=folder_name
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"附件上传失败: {e}")

    att = DocumentAttachment(
        id=body.id,
        document_id=doc_id,
        file_name=body.file_name,
        file_size=result["file_size"],
        file_path=result["file_path"],
    )
    db.add(att)
    db.commit()
    db.refresh(att)
    d.file_name = body.file_name
    d.file_id = att.id
    db.commit()

    ip = request.client.host if request.client else None
    create_log(db, current_user.id, current_user.username, "上传附件", "document_att", str(doc_id), f"文件:{body.file_name}", ip)
    return {"id": att.id, "file_name": att.file_name, "file_size": att.file_size, "created_at": att.created_at}


@router.get("/{doc_id}/attachments/{att_id}")
async def download_attachment(
    doc_id: uuid.UUID,
    att_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_permission("documents.attachment:download")),
):
    from app.file_storage import file_storage

    att = db.query(DocumentAttachment).filter(
        DocumentAttachment.id == att_id, DocumentAttachment.document_id == doc_id
    ).first()
    if not att:
        raise HTTPException(status_code=404, detail="附件不存在")

    doc = db.query(Document).filter(Document.id == doc_id).first()
    if doc:
        enforce_document_content_access(db, current_user, doc)

    file_data = None
    if att.file_path:
        try:
            data = file_storage.read_file(att.file_path)
            if data:
                file_data = base64.b64encode(data).decode("utf-8")
        except Exception as e:
            print(f"[WARNING] {e}")

    return {
        "id": att.id, "document_id": att.document_id,
        "file_name": att.file_name, "file_size": att.file_size,
        "file_data": file_data,
        "created_at": att.created_at,
    }


@router.get("/{doc_id}/attachments/")
async def list_attachments(
    doc_id: uuid.UUID,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_permission("documents.attachment:download")),
):
    atts = (
        db.query(DocumentAttachment)
        .filter(DocumentAttachment.document_id == doc_id)
        .offset(skip)
        .limit(limit)
        .all()
    )
    return [{
        "id": a.id, "document_id": a.document_id,
        "file_name": a.file_name, "file_size": a.file_size, "created_at": a.created_at,
    } for a in atts]


@router.delete("/{doc_id}/attachments/{att_id}")
async def delete_attachment(
    doc_id: uuid.UUID,
    att_id: uuid.UUID,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_permission("documents.attachment:delete")),
):
    from app.file_storage import file_storage

    att = db.query(DocumentAttachment).filter(
        DocumentAttachment.id == att_id, DocumentAttachment.document_id == doc_id
    ).first()
    if not att:
        raise HTTPException(status_code=404, detail="附件不存在")

    if att.file_path:
        try:
            file_storage.delete_file(att.file_path)
        except Exception as e:
            print(f"[WARNING] {e}")

    if is_stp_file(att.file_name):
        delete_glb_cache(str(att.id))

    if is_office_file(att.file_name):
        delete_pdf_cache(str(att.id), att.file_path)

    d = db.query(Document).filter(Document.id == doc_id).first()
    if d and d.file_id == att.id:
        d.file_id = None
        d.file_name = None
    db.delete(att)
    db.commit()
    ip = request.client.host if request.client else None
    create_log(db, current_user.id, current_user.username, "删除附件", "document_att", str(doc_id), f"文件ID:{att_id}", ip)
    return {"message": "附件已删除"}


# ===== 版本控制 (升版) =====

@router.post("/{doc_id}/upgrade")
async def upgrade_document_endpoint(
    doc_id: uuid.UUID,
    body: UpgradeRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_permission("documents:create")),
):
    db_doc, err = upgrade_document(db, doc_id, current_user.real_name or current_user.username)
    if err:
        raise HTTPException(status_code=400, detail=err)
    ip = request.client.host if request.client else None
    create_log(db, current_user.id, current_user.username, "图文档升版", "document", str(db_doc.id), f"编号:{db_doc.code} 版本:{db_doc.version}", ip)
    return {
        "id": db_doc.id, "code": db_doc.code, "name": db_doc.name,
        "version": db_doc.version, "status": db_doc.status,
        "remark": db_doc.remark,
        "file_name": db_doc.file_name, "file_id": db_doc.file_id,
        "created_at": db_doc.created_at, "updated_at": db_doc.updated_at,
    }


@router.get("/{doc_id}/versions")
async def get_document_versions_endpoint(
    doc_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: UserModel = Depends(require_permission("documents:read")),
):
    versions = get_document_versions(db, doc_id)
    return [{
        "id": v.id, "code": v.code, "name": v.name,
        "version": v.version, "status": v.status,
        "remark": v.remark,
        "file_name": v.file_name, "file_id": v.file_id,
        "created_at": v.created_at, "updated_at": v.updated_at,
    } for v in versions]
