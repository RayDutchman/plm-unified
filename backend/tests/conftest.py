"""pytest fixtures：每个测试一个独立 SQLite 内存会话。"""
import os
# 在导入任何 app 模块前设置环境变量，防止 database.py 模块级 create_engine 尝试连 PostgreSQL
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("JWT_SECRET", "test-secret-key-for-tests-only-xx")

import pytest
from sqlalchemy import JSON, create_engine, event
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
import app.models  # noqa: F401  触发全部模型注册到 Base.metadata


@compiles(JSONB, "sqlite")
def _compile_jsonb_sqlite(element, compiler, **kw):
    """测试环境下将 PostgreSQL JSONB 映射为 SQLite 可识别的 JSON 类型。"""
    return compiler.process(JSON())


@pytest.fixture
def db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # SQLite 默认不强制外键，需显式开启，才能测到 ondelete RESTRICT/CASCADE/SET NULL
    @event.listens_for(engine, "connect")
    def _enable_sqlite_fk(dbapi_con, con_record):
        dbapi_con.execute("PRAGMA foreign_keys=ON")

    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
