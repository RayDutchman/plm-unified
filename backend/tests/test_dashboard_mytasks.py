"""我的任务聚合测试：指派给我且未完成的项目任务"""
import uuid
import datetime
import pytest
from app.crud.dashboard_mytasks import get_my_tasks
from app.models.models_project import Project, ProjectTask
from app.models.user import User
from app.models.workspace import Workspace


@pytest.fixture
def workspace(db):
    ws = Workspace(id=uuid.uuid4(), name="test-ws")
    db.add(ws); db.commit()
    return ws


@pytest.fixture
def me(db, workspace):
    u = User(id=uuid.uuid4(), workspace_id=workspace.id, username="me",
             password_hash="h", real_name="我", role="engineer")
    db.add(u); db.commit()
    return u


@pytest.fixture
def other(db, workspace):
    u = User(id=uuid.uuid4(), workspace_id=workspace.id, username="other",
             password_hash="h", real_name="他人", role="engineer")
    db.add(u); db.commit()
    return u


def _project(db, me):
    p = Project(id=uuid.uuid4(), code="PRJ-1", name="项目一", status="进行中", owner_id=me.id)
    db.add(p); db.commit()
    return p


def _task(db, project_id, **kw):
    d = dict(id=uuid.uuid4(), project_id=project_id, code="T-1", name="任务一",
             task_type="任务", status="进行中", priority="中", sort_order=0)
    d.update(kw)
    t = ProjectTask(**d); db.add(t); db.commit()
    return t


def test_assigned_unfinished_included(db, me):
    p = _project(db, me)
    _task(db, p.id, assignee_id=me.id, status="进行中", task_type="里程碑")
    tasks = get_my_tasks(db, me.id)
    assert len(tasks) == 1
    assert tasks[0]["project_name"] == "项目一"
    assert tasks[0]["project_code"] == "PRJ-1"
    assert tasks[0]["name"] == "任务一"
    assert tasks[0]["task_type"] == "里程碑"


def test_finished_excluded(db, me):
    p = _project(db, me)
    _task(db, p.id, assignee_id=me.id, status="已完成")
    assert get_my_tasks(db, me.id) == []


def test_others_task_excluded(db, me, other):
    p = _project(db, me)
    _task(db, p.id, assignee_id=other.id, status="进行中")
    assert get_my_tasks(db, me.id) == []


def test_planned_end_serialized(db, me):
    p = _project(db, me)
    _task(db, p.id, assignee_id=me.id, status="未开始", planned_end=datetime.date(2026, 6, 30))
    tasks = get_my_tasks(db, me.id)
    assert tasks[0]["planned_end"] == "2026-06-30"
