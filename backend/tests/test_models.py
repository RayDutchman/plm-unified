"""M1 数据地基：模型与约束测试（SQLite 内存库）。"""


def test_database_module_exposes_base_and_get_db():
    from app.database import Base, get_db, SessionLocal
    assert Base is not None
    assert callable(get_db)
    assert SessionLocal is not None


import uuid
import pytest
from sqlalchemy.exc import IntegrityError


def test_workspace_and_user_roundtrip(db):
    from app.models import Workspace, User
    ws = Workspace(name="default")
    db.add(ws); db.commit(); db.refresh(ws)
    assert isinstance(ws.id, uuid.UUID)

    user = User(
        workspace_id=ws.id, username="admin", password_hash="x",
        real_name="管理员", role="admin", status="active",
    )
    db.add(user); db.commit(); db.refresh(user)
    assert user.created_at is not None
    assert user.deleted_at is None


def test_user_username_unique(db):
    from app.models import Workspace, User
    ws = Workspace(name="w"); db.add(ws); db.commit()
    db.add(User(workspace_id=ws.id, username="dup", password_hash="x",
                real_name="a", role="admin", status="active"))
    db.commit()
    db.add(User(workspace_id=ws.id, username="dup", password_hash="x",
                real_name="b", role="admin", status="active"))
    with pytest.raises(IntegrityError):
        db.commit()


def _make_ws_user(db):
    from app.models import Workspace, User
    ws = Workspace(name="w"); db.add(ws); db.commit(); db.refresh(ws)
    u = User(workspace_id=ws.id, username="u", password_hash="x",
             real_name="r", role="admin", status="active")
    db.add(u); db.commit(); db.refresh(u)
    return ws, u


def test_part_three_layers_roundtrip(db):
    from app.models import PartMaster, PartRevision, PartIteration
    ws, u = _make_ws_user(db)
    pm = PartMaster(workspace_id=ws.id, number="P-001", name="零件1",
                    standard_part=False, author_id=u.id)
    db.add(pm); db.commit(); db.refresh(pm)

    rev = PartRevision(part_master_id=pm.id, version="A", status="WIP")
    db.add(rev); db.commit(); db.refresh(rev)
    assert rev.checkout_user_id is None

    it = PartIteration(part_revision_id=rev.id, iteration=1, author_id=u.id)
    db.add(it); db.commit(); db.refresh(it)
    assert it.check_in_date is None


def test_part_master_number_unique_per_workspace(db):
    from app.models import PartMaster
    ws, u = _make_ws_user(db)
    db.add(PartMaster(workspace_id=ws.id, number="P-1", name="a", author_id=u.id))
    db.commit()
    db.add(PartMaster(workspace_id=ws.id, number="P-1", name="b", author_id=u.id))
    with pytest.raises(IntegrityError):
        db.commit()


def test_part_iteration_must_be_positive(db):
    from app.models import PartMaster, PartRevision, PartIteration
    ws, u = _make_ws_user(db)
    pm = PartMaster(workspace_id=ws.id, number="P-2", name="a", author_id=u.id)
    db.add(pm); db.commit()
    rev = PartRevision(part_master_id=pm.id, version="A", status="WIP")
    db.add(rev); db.commit()
    db.add(PartIteration(part_revision_id=rev.id, iteration=0, author_id=u.id))
    with pytest.raises(IntegrityError):
        db.commit()


def test_binary_and_geometry_roundtrip(db):
    from app.models import (
        PartMaster, PartRevision, PartIteration, BinaryResource, Geometry,
    )
    ws, u = _make_ws_user(db)
    pm = PartMaster(workspace_id=ws.id, number="P-G", name="a", author_id=u.id)
    db.add(pm); db.commit()
    rev = PartRevision(part_master_id=pm.id, version="A", status="WIP")
    db.add(rev); db.commit()
    it = PartIteration(part_revision_id=rev.id, iteration=1, author_id=u.id)
    db.add(it); db.commit()

    br = BinaryResource(full_name="w/parts/P-G/A/1/geometries/g.glb",
                        content_length=1024)
    db.add(br); db.commit(); db.refresh(br)

    geo = Geometry(iteration_id=it.id, binary_resource_id=br.id, quality=0,
                   x_min=0.0, y_min=0.0, z_min=0.0, x_max=1.0, y_max=1.0, z_max=1.0)
    db.add(geo); db.commit(); db.refresh(geo)
    assert geo.quality == 0


def test_binary_full_name_unique(db):
    from app.models import BinaryResource
    db.add(BinaryResource(full_name="dup/path", content_length=1)); db.commit()
    db.add(BinaryResource(full_name="dup/path", content_length=2))
    with pytest.raises(IntegrityError):
        db.commit()
