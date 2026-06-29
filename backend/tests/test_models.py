"""M1 数据地基：模型与约束测试（SQLite 内存库）。"""


def test_database_module_exposes_base_and_get_db():
    from app.database import Base, get_db, SessionLocal
    assert Base is not None
    assert callable(get_db)
    assert SessionLocal is not None
