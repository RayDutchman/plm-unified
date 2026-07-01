"""应用配置：从环境变量读取，集中管理。"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # 数据库连接串，compose 注入 postgresql://plm:plmpass@db:5432/plm_unified
    database_url: str = "postgresql://plm:plmpass@localhost:5435/plm_unified"
    # JWT 密钥（M1.5 使用），至少 32 字符
    jwt_secret: str = "dev-only-secret-change-me-please-32chars"
    # vault 文件根目录
    vault_path: str = "/vault"
    # conversion 临时文件目录（与 conversion 容器共享）
    conversions_path: str = "/data/conversions"
    redis_url: str = "redis://redis:6379"
    uploads_path: str = "/uploads"
    cors_origins: list[str] = ["https://localhost:8080", "http://localhost:8080"]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
