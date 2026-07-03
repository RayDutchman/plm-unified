"""零件 CRUD 与签入签出状态机。

业务规则来源：DocDoku PartManagerBean / CheckInManager / CheckOutManager
并发保护：签出/签入对 part_revisions 行用 SELECT FOR UPDATE（with_for_update()）
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.part import PartIteration, PartMaster, PartRevision
from app.schemas.part import PartCreate


# ---------------------------------------------------------------------------
# 内部工具
# ---------------------------------------------------------------------------

def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _get_revision_for_update(
    db: Session,
    number: str,
    version: str,
    workspace_id: uuid.UUID,
) -> PartRevision:
    """
    查询指定零件的版本行并加行锁（SELECT FOR UPDATE）。
    master 和 revision 都加锁，防止并发软删除 master 后 revision 查询结果过时。
    未找到抛 404，已软删除抛 404。
    """
    master = (
        db.query(PartMaster)
        .filter(
            PartMaster.workspace_id == workspace_id,
            PartMaster.number == number,
            PartMaster.deleted_at.is_(None),
        )
        .with_for_update()
        .first()
    )
    if not master:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"零件 {number!r} 不存在")

    revision = (
        db.query(PartRevision)
        .filter(
            PartRevision.part_master_id == master.id,
            PartRevision.version == version,
            PartRevision.deleted_at.is_(None),
        )
        .with_for_update()
        .first()
    )
    if not revision:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"零件 {number!r} 版本 {version!r} 不存在",
        )
    return revision


def _latest_iteration(db: Session, revision_id: uuid.UUID) -> PartIteration | None:
    """返回指定版本的最大迭代号记录。"""
    return (
        db.query(PartIteration)
        .filter(PartIteration.part_revision_id == revision_id)
        .order_by(PartIteration.iteration.desc())
        .first()
    )


# ---------------------------------------------------------------------------
# 1.6 CRUD：创建 / 查询
# ---------------------------------------------------------------------------

def create_part(db: Session, data: PartCreate, author_id: uuid.UUID) -> PartMaster:
    """
    原子创建三层：PartMaster + PartRevision(A, WIP) + PartIteration(1, 未签入)。
    对应 DocDoku createPartMaster 行为。
    """
    # 检查同工作空间内编号唯一性（软删除记录不计）
    exists = (
        db.query(PartMaster)
        .filter(
            PartMaster.workspace_id == data.workspace_id,
            PartMaster.number == data.number,
            PartMaster.deleted_at.is_(None),
        )
        .first()
    )
    if exists:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"工作空间内零件编号 {data.number!r} 已存在",
        )

    master = PartMaster(
        id=uuid.uuid4(),
        workspace_id=data.workspace_id,
        number=data.number,
        name=data.name,
        type=data.type,
        standard_part=data.standard_part,
        author_id=author_id,
    )
    db.add(master)
    db.flush()  # 获取 master.id，保持同一事务

    revision = PartRevision(
        id=uuid.uuid4(),
        part_master_id=master.id,
        version="A",
        status="WIP",
        description=data.description,
        # 创建后自动处于签出状态（与 DocDoku createPartMaster 一致）
        checkout_user_id=author_id,
        checkout_date=_utcnow(),
    )
    db.add(revision)
    db.flush()

    iteration = PartIteration(
        id=uuid.uuid4(),
        part_revision_id=revision.id,
        iteration=1,
        author_id=author_id,
        check_in_date=None,  # 未签入
    )
    db.add(iteration)
    db.commit()
    db.refresh(master)
    return master


def get_part(db: Session, number: str, workspace_id: uuid.UUID) -> PartMaster:
    """按编号取零件（含所有版本和迭代）。"""
    master = (
        db.query(PartMaster)
        .filter(
            PartMaster.workspace_id == workspace_id,
            PartMaster.number == number,
            PartMaster.deleted_at.is_(None),
        )
        .first()
    )
    if not master:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"零件 {number!r} 不存在")
    return master


def list_parts(
    db: Session,
    workspace_id: uuid.UUID,
    skip: int = 0,
    limit: int = 50,
) -> list[PartMaster]:
    """列出工作空间内所有未删除的零件，分页。"""
    return (
        db.query(PartMaster)
        .filter(
            PartMaster.workspace_id == workspace_id,
            PartMaster.deleted_at.is_(None),
        )
        .order_by(PartMaster.number)
        .offset(skip)
        .limit(limit)
        .all()
    )


# ---------------------------------------------------------------------------
# 1.7 状态机：签出 / 签入 / 撤销签出
# ---------------------------------------------------------------------------

def checkout(
    db: Session,
    number: str,
    version: str,
    workspace_id: uuid.UUID,
    current_user_id: uuid.UUID,
) -> PartRevision:
    """
    签出零件版本（对齐 DocDoku：checkout 时创建新迭代）。
    规则：
       - status 必须为 WIP
       - checkout_user_id 必须为 NULL
       - 冻结当前迭代 → 创建下一迭代（新迭代可上传/修改）
    并发保护：SELECT FOR UPDATE
    """
    revision = _get_revision_for_update(db, number, version, workspace_id)

    if revision.status != "WIP":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"版本 {version!r} 状态为 {revision.status}，不可签出（仅 WIP 可签出）",
        )
    if revision.checkout_user_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"版本 {version!r} 已被用户 {revision.checkout_user_id} 签出",
        )

    now = _utcnow()

    # 冻结当前迭代（若存在且未冻结）
    latest = _latest_iteration(db, revision.id)
    if latest and latest.check_in_date is None:
        latest.check_in_date = now
        db.flush()

    # 创建新迭代（DocDoku：checkout 时创建，upload/update 写入此迭代）
    max_iter = (
        db.query(func.max(PartIteration.iteration))
        .filter(PartIteration.part_revision_id == revision.id)
        .scalar()
    ) or 0
    new_iter = PartIteration(
        id=uuid.uuid4(),
        part_revision_id=revision.id,
        iteration=max_iter + 1,
        author_id=current_user_id,
        check_in_date=None,
    )
    db.add(new_iter)
    db.flush()

    revision.checkout_user_id = current_user_id
    revision.checkout_date = now
    db.commit()
    db.refresh(revision)
    return revision


def checkin(
    db: Session,
    number: str,
    version: str,
    workspace_id: uuid.UUID,
    current_user_id: uuid.UUID,
    iteration_note: str | None = None,
) -> PartRevision:
    """
    签入零件版本（对齐 DocDoku：checkin 时冻结当前迭代，不创建新迭代）：
       1. 冻结当前最新迭代（写 check_in_date）
       2. 清签出锁
       3. 状态升为 RELEASED
     规则：
       - 必须已签出（checkout_user_id IS NOT NULL）
       - 必须是签出本人
    注意：新迭代在 checkout 时已创建；checkin 只冻结。
    """
    revision = _get_revision_for_update(db, number, version, workspace_id)

    if revision.checkout_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"版本 {version!r} 未签出，无法签入",
        )
    if revision.checkout_user_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"版本 {version!r} 由其他用户签出，无法以当前用户签入",
        )

    now = _utcnow()

    # 冻结当前草稿迭代
    latest = _latest_iteration(db, revision.id)
    if latest is None:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"版本 {version!r} 无任何迭代记录，数据异常",
        )
    if latest.check_in_date is None:
        latest.check_in_date = now
        if iteration_note:
            latest.iteration_note = iteration_note
        db.flush()

    # 清签出锁
    revision.checkout_user_id = None
    revision.checkout_date = None
    revision.status = "RELEASED"
    db.commit()
    db.refresh(revision)
    return revision


def undocheckout(
    db: Session,
    number: str,
    version: str,
    workspace_id: uuid.UUID,
    current_user_id: uuid.UUID,
) -> PartRevision:
    """
    撤销签出：删除 checkout 时创建的新迭代，清签出锁。
    规则：
       - 必须已签出
       - 必须是签出本人
       - 新迭代（check_in_date IS NULL 且 iteration > 1）会被删除，
         原迭代的 check_in_date 恢复为 NULL（解冻）
    """
    revision = _get_revision_for_update(db, number, version, workspace_id)

    if revision.checkout_user_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"版本 {version!r} 未签出，无法撤销",
        )
    if revision.checkout_user_id != current_user_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"版本 {version!r} 由其他用户签出，无法撤销",
        )

    # 删除 checkout 时创建的新迭代（check_in_date IS NULL 且 iteration > 1）
    latest = _latest_iteration(db, revision.id)
    if latest and latest.check_in_date is None and latest.iteration > 1:
        db.delete(latest)
        db.flush()

    # 解冻原迭代
    prev = _latest_iteration(db, revision.id)  # 删掉新迭代后，latest 就是原迭代
    if prev and prev.check_in_date is not None:
        prev.check_in_date = None
        db.flush()

    # 清签出锁
    revision.checkout_user_id = None
    revision.checkout_date = None
    db.commit()
    db.refresh(revision)
    return revision
