from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import auth
from app.routers.parts import router as parts_router
from app.routers.iterations import router as iterations_router
from app.routers.conversion_compat import router as conversion_compat_router
from app.routers.components import router as components_router

app = FastAPI(
    title="PLM Unified API",
    version="0.1.0",
    description="新一代 PLM 系统后端 API",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "https://localhost:8080"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 路由挂载（统一 /api 前缀）
app.include_router(auth.router, prefix="/api")
app.include_router(parts_router)
app.include_router(iterations_router)
app.include_router(conversion_compat_router, prefix="/api")
app.include_router(components_router)

# Phase 1: 实体层（逐步取消注释激活）
from app.routers.users import router as users_router
app.include_router(users_router, prefix="/api")
from app.routers.user_groups import router as user_groups_router
app.include_router(user_groups_router, prefix="/api")
from app.routers.documents import router as documents_router
app.include_router(documents_router, prefix="/api")
from app.routers.attachments_v2 import router as attachments_router
app.include_router(attachments_router, prefix="/api")

# Phase 2: 关系层
from app.routers.bom import router as bom_router
app.include_router(bom_router, prefix="/api")

# Phase 3: 流程层
from app.routers.ecrs import router as ecrs_router
from app.routers.issues import router as issues_router
app.include_router(ecrs_router, prefix="/api")
app.include_router(issues_router, prefix="/api")
from app.routers.ecos import router as ecos_router
app.include_router(ecos_router, prefix="/api")

# Phase 4: 构型+库存+项目
from app.routers.configuration import router as configuration_router
app.include_router(configuration_router, prefix="/api")
from app.routers.inventory import router as inventory_router
app.include_router(inventory_router, prefix="/api")
from app.routers.projects import router as projects_router
app.include_router(projects_router, prefix="/api")

# Phase 5: 支撑层
from app.routers.dashboard import router as dashboard_router
app.include_router(dashboard_router, prefix="/api")
from app.routers.custom_fields import router as custom_fields_router
app.include_router(custom_fields_router, prefix="/api")
from app.routers.logs import router as logs_router
app.include_router(logs_router, prefix="/api")
from app.routers.admin import router as admin_router
app.include_router(admin_router, prefix="/api")
from app.routers.sync import router as sync_router
app.include_router(sync_router, prefix="/api")


@app.get("/health", tags=["系统"])
async def health_check():
    """健康检查接口"""
    return {"status": "ok", "version": "0.1.0"}
