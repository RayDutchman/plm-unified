from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from typing import Optional

from app.database import get_db
from app.models import User
from app.permissions import require_permission

router = APIRouter(prefix="/admin", tags=["数据管理"])


@router.get("/soft-deleted-stats")
async def get_soft_deleted_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("admin.soft_delete:read"))
):
    tables = ["documents", "ecrs", "ecos", "configuration_items", "part_masters", "part_revisions"]
    stats = {}

    for tbl in tables:
        result = db.execute(text(f"""
            SELECT 
                COUNT(*) as count,
                MIN(deleted_at)::timestamptz as earliest,
                MAX(deleted_at)::timestamptz as latest
            FROM {tbl}
            WHERE deleted_at IS NOT NULL
        """))
        row = result.fetchone()
        stats[tbl] = {
            "count": row[0] or 0,
            "earliest": row[1].isoformat() if row[1] else None,
            "latest": row[2].isoformat() if row[2] else None,
        }

    return stats


@router.post("/purge-soft-deleted")
async def purge_soft_deleted(
    body: dict,
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("admin.soft_delete:cleanup"))
):
    if not body.get("confirm"):
        raise HTTPException(status_code=400, detail="需要确认操作（confirm: true）")

    tables = body.get("tables", [])
    if not tables:
        raise HTTPException(status_code=400, detail="请指定要清理的表")

    allowed_tables = {"documents", "ecrs", "ecos", "configuration_items", "part_masters", "part_revisions"}
    for tbl in tables:
        if tbl not in allowed_tables:
            raise HTTPException(status_code=400, detail=f"无效的表名: {tbl}")

    before_date = body.get("before_date")

    purge_order = ["part_revisions", "part_masters", "ecos", "ecrs", "configuration_items", "documents"]
    ordered = [t for t in purge_order if t in tables]

    deleted_counts = {}
    skipped = {}
    for tbl in ordered:
        try:
            with db.begin_nested():
                if before_date:
                    result = db.execute(text(f"""
                        DELETE FROM {tbl}
                        WHERE deleted_at IS NOT NULL AND deleted_at < :before_date
                    """), {"before_date": before_date})
                else:
                    result = db.execute(text(f"""
                        DELETE FROM {tbl}
                        WHERE deleted_at IS NOT NULL
                    """))
                deleted_counts[tbl] = result.rowcount
        except IntegrityError as e:
            deleted_counts[tbl] = 0
            ref_table = getattr(getattr(e.orig, "diag", None), "table_name", None)
            skipped[tbl] = (
                f"仍被「{ref_table}」表中的现有记录引用，无法清理" if ref_table
                else "仍被其他现有记录引用，无法清理"
            )

    db.commit()

    ip = request.client.host if request.client else None
    from app.crud import create_log
    detail = f"清理了 {sum(deleted_counts.values())} 条记录: {deleted_counts}"
    if skipped:
        detail += f"；跳过: {skipped}"
    create_log(
        db, current_user.id, current_user.username,
        "清除软删除数据", "admin", "purge",
        detail,
        ip
    )

    return {
        "deleted_counts": deleted_counts,
        "skipped": skipped,
        "total": sum(deleted_counts.values())
    }
