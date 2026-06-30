from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import auth
from app.routers.parts import router as parts_router
from app.routers.iterations import router as iterations_router
from app.routers.conversion_compat import router as conversion_compat_router

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


@app.get("/health", tags=["系统"])
async def health_check():
    """健康检查接口"""
    return {"status": "ok", "version": "0.1.0"}
