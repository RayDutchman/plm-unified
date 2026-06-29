from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers.parts import router as parts_router

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

# 注册路由
app.include_router(parts_router)


@app.get("/health", tags=["系统"])
async def health_check():
    """健康检查接口"""
    return {"status": "ok", "version": "0.1.0"}
