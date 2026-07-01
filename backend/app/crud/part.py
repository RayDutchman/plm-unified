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
    updated_since: float | None = None,
) -> list[PartMaster]:
    """列出工作空间内所有未删除的零件，分页。updated_since 为 UNIX 时间戳时，包含该时间之后的已删除记录。"""
    from datetime import datetime, timezone
    query = db.query(PartMaster).filter(PartMaster.workspace_id == workspace_id)
    if updated_since is not None:
        since_dt = datetime.fromtimestamp(updated_since, tz=timezone.utc)
        query = query.filter(
            (PartMaster.updated_at >= since_dt)
            | (PartMaster.deleted_at >= since_dt)
        )
    else:
        query = query.filter(PartMaster.deleted_at.is_(None))
    return (
        query.order_by(PartMaster.number)
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
    签出零件版本。
    规则：
      - status 必须为 WIP（已发布/废弃版本不可签出）
      - checkout_user_id 必须为 NULL（未被任何人签出）
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

    revision.checkout_user_id = current_user_id
    revision.checkout_date = _utcnow()
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
    签入零件版本：
      1. 冻结当前最新迭代（写 check_in_date）
      2. 生成下一迭代号（max+1，并发安全）
      3. 清签出锁
    规则：
      - 必须已签出（checkout_user_id IS NOT NULL）
      - 必须是签出本人
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

    # 冻结当前草稿迭代（正常情况下必然存在，否则数据不一致）
    latest = _latest_iteration(db, revision.id)
    if latest is None:
        # 防御性检查：版本无任何迭代，属于数据异常，回滚并报 500
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"版本 {version!r} 无任何迭代记录，数据异常",
        )
    if latest.check_in_date is None:
        latest.check_in_date = now
        if iteration_note:
            latest.iteration_note = iteration_note
        db.flush()

    # 生成下一迭代（max+1，并发安全）
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

    # 清签出锁
    revision.checkout_user_id = None
    revision.checkout_date = None
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
    撤销签出：丢弃未签入的草稿迭代（若存在且 iteration > 1），清签出锁。
    规则：
      - 必须已签出
      - 必须是签出本人
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

    # 删除草稿迭代（check_in_date IS NULL 且 iteration > 1）
    latest = _latest_iteration(db, revision.id)
    if latest and latest.check_in_date is None and latest.iteration > 1:
        db.delete(latest)
        db.flush()

    # 清签出锁
    revision.checkout_user_id = None
    revision.checkout_date = None
    db.commit()
    db.refresh(revision)
    return revision
