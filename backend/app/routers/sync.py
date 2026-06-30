"""同步状态查询。"""
from fastapi import APIRouter

router = APIRouter(prefix="/sync", tags=["同步"])


@router.get("/status")
def get_sync_status():
    return {
        "parts": 0,
        "assemblies": 0,
        "documents": 0,
        "bom_items": 0,
        "ecrs": 0,
        "ecos": 0,
        "config_items": 0,
    }
