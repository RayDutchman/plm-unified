"""同步状态查询。"""
import calendar
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.models.part import PartMaster
from app.models.models_document import Document
from app.models.models_ecr import ECR
from app.models.models_eco import ECO
from app.models.models_configuration import ConfigurationItem
from app.permissions import require_permission

router = APIRouter(prefix="/sync", tags=["同步"])


def _max_ts(db: Session, model, col) -> float:
    val = db.query(func.max(col)).scalar()
    if val is None:
        return 0
    return calendar.timegm(val.utctimetuple()) + val.microsecond / 1_000_000


@router.get("/status")
def get_sync_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("sync:read"))
):
    return {
        "parts": _max_ts(db, PartMaster, PartMaster.updated_at),
        "assemblies": _max_ts(db, PartMaster, PartMaster.updated_at),
        "documents": _max_ts(db, Document, Document.updated_at),
        "bom_items": 0,
        "ecrs": _max_ts(db, ECR, ECR.updated_at),
        "ecos": _max_ts(db, ECO, ECO.updated_at),
        "config_items": _max_ts(db, ConfigurationItem, ConfigurationItem.updated_at),
    }
