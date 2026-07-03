"""待我处理聚合测试：ECR/ECO 待我审批 + 我发起被驳回"""
import uuid
import pytest
from app.crud.dashboard_todos import get_my_todos
from app.models.models_ecr import ECR, ECRReviewRecord
from app.models.models_eco import ECO, ECOReviewRecord
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


def _ecr(**kw):
    d = dict(id=uuid.uuid4(), ecr_number="ECR-1", title="改规格", reason="x",
             priority="high", status="reviewing", reviewers=[], creator_id=uuid.uuid4())
    d.update(kw)
    return ECR(**d)


def _eco(**kw):
    d = dict(id=uuid.uuid4(), eco_number="ECO-1", title="改规格", reason="x",
             priority="high", status="reviewing", reviewers=[], creator_id=uuid.uuid4())
    d.update(kw);
    return ECO(**d)


def test_ecr_pending_my_review_included(db, me, other):
    ecr = _ecr(reviewers=[{"user_id": str(me.id), "user_name": "我", "role": "r", "seq": 1}], creator_id=other.id)
    db.add(ecr); db.commit()
    todos = get_my_todos(db, me.id)
    assert len(todos) == 1
    assert todos[0]["type"] == "ecr"
    assert todos[0]["kind"] == "review"
    assert todos[0]["number"] == "ECR-1"


def test_ecr_already_reviewed_excluded(db, me, other):
    ecr = _ecr(reviewers=[{"user_id": str(me.id), "seq": 1}], creator_id=other.id)
    db.add(ecr); db.commit()
    db.add(ECRReviewRecord(ecr_id=ecr.id, reviewer_id=me.id, decision="approved")); db.commit()
    assert get_my_todos(db, me.id) == []


def test_my_rejected_ecr_included(db, me):
    ecr = _ecr(status="rejected", creator_id=me.id, reviewers=[])
    db.add(ecr); db.commit()
    todos = get_my_todos(db, me.id)
    assert len(todos) == 1
    assert todos[0]["kind"] == "rejected"


def test_not_reviewing_not_mine_excluded(db, me, other):
    db.add(_ecr(status="draft", reviewers=[{"user_id": str(other.id)}], creator_id=other.id)); db.commit()
    assert get_my_todos(db, me.id) == []


def test_eco_pending_my_review_included(db, me, other):
    eco = _eco(reviewers=[{"user_id": str(me.id), "user_name": "我", "role": "r", "seq": 1}], creator_id=other.id)
    db.add(eco); db.commit()
    todos = get_my_todos(db, me.id)
    assert len(todos) == 1
    assert todos[0]["type"] == "eco"
    assert todos[0]["kind"] == "review"


def test_eco_already_reviewed_excluded(db, me, other):
    eco = _eco(reviewers=[{"user_id": str(me.id), "seq": 1}], creator_id=other.id)
    db.add(eco); db.commit()
    db.add(ECOReviewRecord(eco_id=eco.id, reviewer_id=me.id, decision="approved")); db.commit()
    assert get_my_todos(db, me.id) == []


def test_my_rejected_eco_included(db, me):
    eco = _eco(status="rejected", creator_id=me.id, reviewers=[])
    db.add(eco); db.commit()
    todos = get_my_todos(db, me.id)
    assert len(todos) == 1
    assert todos[0]["kind"] == "rejected"
