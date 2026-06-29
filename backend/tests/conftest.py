"""pytest fixtures：每个测试一个独立 SQLite 内存会话。"""
import os
os.environ.setdefault("JWT_SECRET", "test-secret-key-for-tests-only-xx")

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
import app.models  # noqa: F401  触发全部模型注册到 Base.metadata


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
