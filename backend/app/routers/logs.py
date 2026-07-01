from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional

from app.database import get_db
from app.models import User
from app.crud import get_logs
from app.permissions import require_permission

router = APIRouter(prefix="/logs", tags=["操作日志"])

@router.get("/")
async def list_logs(skip: int = 0, limit: int = 100,
                    target_type: Optional[str] = Query(None),
                    target_id: Optional[str] = Query(None),
                    db: Session = Depends(get_db),
                    current_user: User = Depends(require_permission("logs:read"))):
    items, total = get_logs(db, skip=skip, limit=limit, target_type=target_type, target_id=target_id)
    return {"items": items, "total": total}
