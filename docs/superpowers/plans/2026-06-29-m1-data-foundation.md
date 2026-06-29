# M1 数据地基（ORM 模型 + Alembic）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 plm-unified 后端落地 DocDoku 三层零件模型的全部 9 张核心表（SQLAlchemy ORM）与可建库/回滚的 Alembic 首版迁移，作为 M1 任务 1.4，解冻 A 的 CRUD/签入签出工作。

**Architecture:** 纯数据层，模型只依赖 `Base`，不反向依赖 CRUD/路由。模型用 SQLAlchemy 2.0 跨方言类型（`Uuid`/`Double`/`BigInteger`/`DateTime(timezone=True)`），使单元测试可跑 SQLite 内存库（对齐 myPDM 习惯），而 Alembic `--autogenerate` 对真实 PostgreSQL 生成正确 DDL。UUID 应用侧生成（`default=uuid.uuid4`），枚举用 `VARCHAR + CHECK`，软删除/时间戳用 Mixin 复用。

**Tech Stack:** Python 3.12、SQLAlchemy 2.0.36、Alembic 1.14.0、psycopg2-binary、pytest、SQLite（测试）/PostgreSQL 15（运行）。

---

## 对应规格

实现 [`docs/collaboration/m1-execution-plan.md`](../../collaboration/m1-execution-plan.md) §四（Phase 0 / 任务 1.4）。本计划**不含** 1.5 认证（后续单独计划）。

## 前置约定（来自规格的已决策项）

- **建表范围**：一次建齐 9 张表 — `workspaces`、`users`、`part_masters`、`part_revisions`、`part_iterations`、`binary_resources`、`geometries`、`part_usage_links`、`cad_instances`。
- **UUID**：应用侧 `default=uuid.uuid4`，类型用通用 `Uuid(as_uuid=True)`。
- **枚举**：`part_revisions.status`、`cad_instances.rotation_type` 用 `String + CheckConstraint`。
- **连接**：从环境变量 `DATABASE_URL` 读（compose 已注入 `postgresql://plm:plmpass@db:5432/plm_unified`）。
- **保留字**：`part_usage_links.order`、`cad_instances.order` 是 SQL 保留字，列名写 `"order"`，SQLAlchemy 自动加引号；Python 属性用 `order`。

## File Structure

| 文件 | 职责 |
|---|---|
| `backend/app/core/config.py` | pydantic-settings：`database_url`、`jwt_secret`、`vault_path` |
| `backend/app/database.py` | `engine`、`SessionLocal`、`Base`、`get_db()` |
| `backend/app/models/mixins.py` | `TimestampMixin`（created_at/updated_at）、`SoftDeleteMixin`（deleted_at） |
| `backend/app/models/workspace.py` | `Workspace` |
| `backend/app/models/user.py` | `User` |
| `backend/app/models/part.py` | `PartMaster` / `PartRevision` / `PartIteration` |
| `backend/app/models/binary.py` | `BinaryResource` / `Geometry` |
| `backend/app/models/assembly.py` | `PartUsageLink` / `CADInstance` |
| `backend/app/models/__init__.py` | 汇总 re-export，供 `from app import models` 与 Alembic 发现 |
| `backend/alembic.ini` | Alembic 配置 |
| `backend/migrations/env.py` | `target_metadata = Base.metadata`，从 `DATABASE_URL` 读连接 |
| `backend/migrations/script.py.mako` | 迁移模板（alembic init 生成） |
| `backend/migrations/versions/0001_initial_schema.py` | 首版迁移（autogenerate + 人工校订 + 默认 workspace 种子） |
| `backend/tests/conftest.py` | SQLite 内存库 fixture |
| `backend/tests/test_models.py` | 模型 round-trip 与约束测试 |

所有命令默认在 `backend/` 目录下执行；先 `pip install -r requirements.txt`。

---

### Task 1: 配置与数据库会话层

**Files:**
- Create: `backend/app/core/config.py`
- Create: `backend/app/database.py`
- Test: `backend/tests/test_models.py`（本任务先建文件 + 冒烟用例）
- Create: `backend/tests/__init__.py`（空文件）

- [ ] **Step 1: 写失败测试**

`backend/tests/test_models.py`：
```python
"""M1 数据地基：模型与约束测试（SQLite 内存库）。"""

def test_database_module_exposes_base_and_get_db():
    from app.database import Base, get_db, SessionLocal
    assert Base is not None
    assert callable(get_db)
    assert SessionLocal is not None
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_models.py::test_database_module_exposes_base_and_get_db -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.database'`

- [ ] **Step 3: 写 config.py**

`backend/app/core/config.py`：
```python
"""应用配置：从环境变量读取，集中管理。"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # 数据库连接串，compose 注入 postgresql://plm:plmpass@db:5432/plm_unified
    database_url: str = "postgresql://plm:plmpass@localhost:5435/plm_unified"
    # JWT 密钥（M1.5 使用），至少 32 字符
    jwt_secret: str = "dev-only-secret-change-me-please-32chars"
    # vault 文件根目录
    vault_path: str = "/vault"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
```

- [ ] **Step 4: 写 database.py**

`backend/app/database.py`：
```python
"""SQLAlchemy 引擎、会话、声明基类与依赖注入。"""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from app.core.config import settings

engine = create_engine(settings.database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI 依赖：每请求一个会话，结束后关闭。"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

- [ ] **Step 5: 创建空 `backend/tests/__init__.py`**

```bash
: > tests/__init__.py
```

- [ ] **Step 6: 跑测试确认通过**

Run: `python -m pytest tests/test_models.py::test_database_module_exposes_base_and_get_db -v`
Expected: PASS

- [ ] **Step 7: 提交**

```bash
git add backend/app/core/config.py backend/app/database.py backend/tests/__init__.py backend/tests/test_models.py
git commit -m "feat(part-api): 添加配置与数据库会话层"
```

---

### Task 2: Mixin + Workspace + User 模型

**Files:**
- Create: `backend/app/models/mixins.py`
- Create: `backend/app/models/workspace.py`
- Create: `backend/app/models/user.py`
- Create: `backend/tests/conftest.py`
- Modify: `backend/tests/test_models.py`

- [ ] **Step 1: 写 conftest（SQLite 内存库 fixture）**

`backend/tests/conftest.py`：
```python
"""pytest fixtures：每个测试一个独立 SQLite 内存会话。"""
import os
os.environ.setdefault("JWT_SECRET", "test-secret-key-for-tests-only-xx")

import pytest
from sqlalchemy import create_engine
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
    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
```

- [ ] **Step 2: 写失败测试**

追加到 `backend/tests/test_models.py`：
```python
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
```

- [ ] **Step 3: 跑测试确认失败**

Run: `python -m pytest tests/test_models.py -k "workspace or username_unique" -v`
Expected: FAIL — `ImportError: cannot import name 'Workspace'`

- [ ] **Step 4: 写 mixins.py**

`backend/app/models/mixins.py`：
```python
"""模型公共 Mixin：时间戳与软删除。"""
from sqlalchemy import Column, DateTime, func


class TimestampMixin:
    # 自动维护：插入设 now，更新刷新 updated_at
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


class SoftDeleteMixin:
    # 软删除标记：非空表示已删除
    deleted_at = Column(DateTime(timezone=True), nullable=True)
```

- [ ] **Step 5: 写 workspace.py**

`backend/app/models/workspace.py`：
```python
"""工作空间。对应 DocDoku Workspace。"""
import uuid
from sqlalchemy import Column, String, Text, Uuid
from app.database import Base
from app.models.mixins import TimestampMixin, SoftDeleteMixin


class Workspace(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "workspaces"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(100), nullable=False, unique=True)  # 工作空间标识
    description = Column(Text, nullable=True)
```

- [ ] **Step 6: 写 user.py**

`backend/app/models/user.py`：
```python
"""登录用户。对应 DocDoku User，新增 workspace_id 归属。"""
import uuid
from sqlalchemy import Column, String, Uuid, ForeignKey
from app.database import Base
from app.models.mixins import TimestampMixin, SoftDeleteMixin


class User(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "users"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(Uuid(as_uuid=True), ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False)
    username = Column(String(64), nullable=False, unique=True)
    password_hash = Column(String(255), nullable=False)
    real_name = Column(String(64), nullable=False)
    role = Column(String(32), nullable=False)
    department = Column(String(128), nullable=True)
    phone = Column(String(32), nullable=True)
    status = Column(String(32), nullable=False, default="active")
```

- [ ] **Step 7: 临时让 `app.models` 可导入这两个模型**

`backend/app/models/__init__.py`（Task 6 会补全其余）：
```python
from app.models.workspace import Workspace
from app.models.user import User

__all__ = ["Workspace", "User"]
```

- [ ] **Step 8: 跑测试确认通过**

Run: `python -m pytest tests/test_models.py -k "workspace or username_unique" -v`
Expected: PASS（2 passed）

- [ ] **Step 9: 提交**

```bash
git add backend/app/models/ backend/tests/conftest.py backend/tests/test_models.py
git commit -m "feat(part-api): 添加 Workspace/User 模型与软删除时间戳 Mixin"
```

---

### Task 3: 零件三层模型（PartMaster / PartRevision / PartIteration）

**Files:**
- Create: `backend/app/models/part.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/tests/test_models.py`

- [ ] **Step 1: 写失败测试**

追加到 `backend/tests/test_models.py`：
```python
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
```

> 注：SQLite 默认不强制 CHECK 之外的部分，但**会**强制 `CheckConstraint` 与 `UniqueConstraint`，故上述断言有效。

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_models.py -k part -v`
Expected: FAIL — `ImportError: cannot import name 'PartMaster'`

- [ ] **Step 3: 写 part.py**

`backend/app/models/part.py`：
```python
"""零件三层模型。对应 DocDoku PartMaster / PartRevision / PartIteration。"""
import uuid
from sqlalchemy import (
    Column, String, Text, Integer, Boolean, Uuid, ForeignKey, DateTime,
    UniqueConstraint, CheckConstraint, func,
)
from app.database import Base
from app.models.mixins import TimestampMixin, SoftDeleteMixin


class PartMaster(Base, TimestampMixin, SoftDeleteMixin):
    """零件主数据。workspace_id + number 唯一。"""
    __tablename__ = "part_masters"
    __table_args__ = (UniqueConstraint("workspace_id", "number", name="uq_part_master_ws_number"),)

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    workspace_id = Column(Uuid(as_uuid=True), ForeignKey("workspaces.id", ondelete="RESTRICT"), nullable=False)
    number = Column(String(100), nullable=False)
    name = Column(String(255), nullable=False)
    type = Column(String(50), nullable=True)
    standard_part = Column(Boolean, nullable=False, default=False)
    author_id = Column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)


class PartRevision(Base, TimestampMixin, SoftDeleteMixin):
    """零件版本（A/B/C…）。状态机 WIP→RELEASED→OBSOLETE。"""
    __tablename__ = "part_revisions"
    __table_args__ = (
        UniqueConstraint("part_master_id", "version", name="uq_part_revision_master_version"),
        CheckConstraint("status IN ('WIP','RELEASED','OBSOLETE')", name="ck_part_revision_status"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    part_master_id = Column(Uuid(as_uuid=True), ForeignKey("part_masters.id", ondelete="CASCADE"), nullable=False)
    version = Column(String(10), nullable=False)
    status = Column(String(20), nullable=False, default="WIP")
    description = Column(Text, nullable=True)
    # 签出锁：非空表示已被该用户签出
    checkout_user_id = Column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    checkout_date = Column(DateTime(timezone=True), nullable=True)
    released_by_id = Column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    released_at = Column(DateTime(timezone=True), nullable=True)
    obsoleted_by_id = Column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    obsoleted_at = Column(DateTime(timezone=True), nullable=True)


class PartIteration(Base, TimestampMixin):
    """零件迭代（1/2/3…）。签入后 check_in_date 非空即冻结。"""
    __tablename__ = "part_iterations"
    __table_args__ = (
        UniqueConstraint("part_revision_id", "iteration", name="uq_part_iteration_revision_iter"),
        CheckConstraint("iteration > 0", name="ck_part_iteration_positive"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    part_revision_id = Column(Uuid(as_uuid=True), ForeignKey("part_revisions.id", ondelete="CASCADE"), nullable=False)
    iteration = Column(Integer, nullable=False)
    iteration_note = Column(Text, nullable=True)
    native_cad_file_id = Column(Uuid(as_uuid=True), ForeignKey("binary_resources.id", ondelete="SET NULL"), nullable=True)
    check_in_date = Column(DateTime(timezone=True), nullable=True)
    author_id = Column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
```

> `native_cad_file_id` 外键指向 `binary_resources`（Task 4 建表）。SQLite `create_all` 按依赖排序，但 Task 4 之前单独跑本任务测试时该表尚不存在——因此本任务测试在 Task 4 完成后整体再跑一次即可全绿；本步只需 part 相关用例通过，`binary_resources` 表由 `create_all` 一并创建（Task 4 的模型已在 metadata 中后才有）。**执行顺序：先做 Task 4 的模型，或本任务测试中容忍该 FK——见 Step 5。**

- [ ] **Step 4: 在 `__init__.py` 注册 part 模型**

`backend/app/models/__init__.py` 改为：
```python
from app.models.workspace import Workspace
from app.models.user import User
from app.models.part import PartMaster, PartRevision, PartIteration

__all__ = ["Workspace", "User", "PartMaster", "PartRevision", "PartIteration"]
```

- [ ] **Step 5: 临时桩表，保证本任务可独立跑**

为避免 `native_cad_file_id` 指向尚不存在的 `binary_resources` 导致 `create_all` 报错，**本任务先把 Task 4 的 binary 模型一并建好再继续**（即合并执行 Task 3 与 Task 4 的模型文件，测试分两次写）。在 `__init__.py` 追加：
```python
from app.models.binary import BinaryResource, Geometry  # 见 Task 4
__all__ += ["BinaryResource", "Geometry"]
```
并先创建 Task 4 的 `binary.py`（仅模型，测试留到 Task 4）。

- [ ] **Step 6: 跑测试确认通过**

Run: `python -m pytest tests/test_models.py -k part -v`
Expected: PASS（3 passed）

- [ ] **Step 7: 提交**

```bash
git add backend/app/models/part.py backend/app/models/binary.py backend/app/models/__init__.py backend/tests/test_models.py
git commit -m "feat(part-api): 添加零件三层模型与唯一/CHECK 约束"
```

---

### Task 4: 二进制资源与几何体（BinaryResource / Geometry）

**Files:**
- Create: `backend/app/models/binary.py`（Task 3 已创建模型，本任务补测试）
- Modify: `backend/tests/test_models.py`

- [ ] **Step 1: 写失败测试**

追加到 `backend/tests/test_models.py`：
```python
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
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_models.py -k "binary or geometry" -v`
Expected: 若 Task 3 Step 5 已建 binary.py 模型则可能直接 PASS；若未建则 FAIL `ImportError`。FAIL 时执行 Step 3。

- [ ] **Step 3: 写 binary.py**

`backend/app/models/binary.py`：
```python
"""二进制资源与几何体。对应 DocDoku BinaryResource / Geometry。"""
import uuid
from sqlalchemy import (
    Column, String, BigInteger, Integer, Double, Uuid, ForeignKey, DateTime, func,
)
from app.database import Base


class BinaryResource(Base):
    """文件元数据，实际文件在 vault。full_name 为全局唯一路径键。"""
    __tablename__ = "binary_resources"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    full_name = Column(String(500), nullable=False, unique=True)
    content_length = Column(BigInteger, nullable=False, default=0)
    last_modified = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Geometry(Base):
    """迭代的 LOD 几何体，含包围盒（毫米）。"""
    __tablename__ = "geometries"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    iteration_id = Column(Uuid(as_uuid=True), ForeignKey("part_iterations.id", ondelete="CASCADE"), nullable=False)
    binary_resource_id = Column(Uuid(as_uuid=True), ForeignKey("binary_resources.id", ondelete="RESTRICT"), nullable=False)
    quality = Column(Integer, nullable=False, default=0)  # 0=最高 LOD
    x_min = Column(Double, nullable=False)
    y_min = Column(Double, nullable=False)
    z_min = Column(Double, nullable=False)
    x_max = Column(Double, nullable=False)
    y_max = Column(Double, nullable=False)
    z_max = Column(Double, nullable=False)
```

- [ ] **Step 4: 跑测试确认通过**

Run: `python -m pytest tests/test_models.py -k "binary or geometry" -v`
Expected: PASS（2 passed）

- [ ] **Step 5: 提交**

```bash
git add backend/app/models/binary.py backend/tests/test_models.py
git commit -m "feat(part-api): 添加 BinaryResource/Geometry 模型"
```

---

### Task 5: 装配关系模型（PartUsageLink / CADInstance）

**Files:**
- Create: `backend/app/models/assembly.py`
- Modify: `backend/app/models/__init__.py`
- Modify: `backend/tests/test_models.py`

- [ ] **Step 1: 写失败测试**

追加到 `backend/tests/test_models.py`：
```python
def test_usage_link_and_cad_instance_roundtrip(db):
    from app.models import (
        PartMaster, PartRevision, PartIteration, PartUsageLink, CADInstance,
    )
    ws, u = _make_ws_user(db)
    parent = PartMaster(workspace_id=ws.id, number="ASM", name="装配", author_id=u.id)
    child = PartMaster(workspace_id=ws.id, number="CHILD", name="子件", author_id=u.id)
    db.add_all([parent, child]); db.commit()
    rev = PartRevision(part_master_id=parent.id, version="A", status="WIP")
    db.add(rev); db.commit()
    it = PartIteration(part_revision_id=rev.id, iteration=1, author_id=u.id)
    db.add(it); db.commit()

    link = PartUsageLink(parent_iteration_id=it.id, component_master_id=child.id,
                         amount=2.0, unit="ea", optional=False, order=0)
    db.add(link); db.commit(); db.refresh(link)

    inst = CADInstance(usage_link_id=link.id, tx=0, ty=0, tz=0,
                       rotation_type="ANGLE", rx=0, ry=0, rz=0, order=0)
    db.add(inst); db.commit(); db.refresh(inst)
    assert inst.rotation_type == "ANGLE"


def test_cad_instance_rotation_type_check(db):
    from app.models import (
        PartMaster, PartRevision, PartIteration, PartUsageLink, CADInstance,
    )
    ws, u = _make_ws_user(db)
    pm = PartMaster(workspace_id=ws.id, number="ASM2", name="a", author_id=u.id)
    db.add(pm); db.commit()
    rev = PartRevision(part_master_id=pm.id, version="A", status="WIP"); db.add(rev); db.commit()
    it = PartIteration(part_revision_id=rev.id, iteration=1, author_id=u.id); db.add(it); db.commit()
    link = PartUsageLink(parent_iteration_id=it.id, component_master_id=pm.id,
                         amount=1.0, unit="ea", optional=False, order=0)
    db.add(link); db.commit()
    db.add(CADInstance(usage_link_id=link.id, tx=0, ty=0, tz=0,
                       rotation_type="BOGUS", order=0))
    with pytest.raises(IntegrityError):
        db.commit()
```

- [ ] **Step 2: 跑测试确认失败**

Run: `python -m pytest tests/test_models.py -k "usage_link or rotation_type" -v`
Expected: FAIL — `ImportError: cannot import name 'PartUsageLink'`

- [ ] **Step 3: 写 assembly.py**

`backend/app/models/assembly.py`：
```python
"""装配关系。对应 DocDoku PartUsageLink / CADInstance。"""
import uuid
from sqlalchemy import (
    Column, String, Text, Integer, Boolean, Double, Uuid, ForeignKey, CheckConstraint,
)
from app.database import Base


class PartUsageLink(Base):
    """父迭代使用子零件（BOM）。子件引用 part_masters（非具体版本）。"""
    __tablename__ = "part_usage_links"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    parent_iteration_id = Column(Uuid(as_uuid=True), ForeignKey("part_iterations.id", ondelete="CASCADE"), nullable=False)
    component_master_id = Column(Uuid(as_uuid=True), ForeignKey("part_masters.id", ondelete="RESTRICT"), nullable=False)
    amount = Column(Double, nullable=False, default=1.0)
    unit = Column(String(20), nullable=True)
    optional = Column(Boolean, nullable=False, default=False)
    # "order" 是 SQL 保留字，SQLAlchemy 自动加引号
    order = Column("order", Integer, nullable=False, default=0)
    comment = Column(Text, nullable=True)


class CADInstance(Base):
    """子件在父装配中的一次位置实例。ANGLE=欧拉角 / MATRIX=3x3 旋转矩阵。"""
    __tablename__ = "cad_instances"
    __table_args__ = (
        CheckConstraint("rotation_type IN ('ANGLE','MATRIX')", name="ck_cad_instance_rotation_type"),
    )

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    usage_link_id = Column(Uuid(as_uuid=True), ForeignKey("part_usage_links.id", ondelete="CASCADE"), nullable=False)
    tx = Column(Double, nullable=False, default=0.0)
    ty = Column(Double, nullable=False, default=0.0)
    tz = Column(Double, nullable=False, default=0.0)
    rotation_type = Column(String(10), nullable=False)
    # ANGLE 模式：欧拉角（弧度）
    rx = Column(Double, nullable=True)
    ry = Column(Double, nullable=True)
    rz = Column(Double, nullable=True)
    # MATRIX 模式：3x3 旋转矩阵（列优先）
    m00 = Column(Double, nullable=True); m01 = Column(Double, nullable=True); m02 = Column(Double, nullable=True)
    m10 = Column(Double, nullable=True); m11 = Column(Double, nullable=True); m12 = Column(Double, nullable=True)
    m20 = Column(Double, nullable=True); m21 = Column(Double, nullable=True); m22 = Column(Double, nullable=True)
    order = Column("order", Integer, nullable=False, default=0)
```

- [ ] **Step 4: 注册到 `__init__.py`**

`backend/app/models/__init__.py` 末尾追加：
```python
from app.models.assembly import PartUsageLink, CADInstance
__all__ += ["PartUsageLink", "CADInstance"]
```

- [ ] **Step 5: 跑测试确认通过**

Run: `python -m pytest tests/test_models.py -k "usage_link or rotation_type" -v`
Expected: PASS（2 passed）

- [ ] **Step 6: 全量回归**

Run: `python -m pytest tests/test_models.py -v`
Expected: 全部 PASS（约 11 用例）

- [ ] **Step 7: 提交**

```bash
git add backend/app/models/assembly.py backend/app/models/__init__.py backend/tests/test_models.py
git commit -m "feat(part-api): 添加 PartUsageLink/CADInstance 装配模型"
```

---

### Task 6: 元数据完整性校验（9 张表）

**Files:**
- Modify: `backend/tests/test_models.py`

- [ ] **Step 1: 写失败测试**

追加到 `backend/tests/test_models.py`：
```python
def test_metadata_has_all_nine_tables():
    from app.database import Base
    import app.models  # noqa: F401
    expected = {
        "workspaces", "users", "part_masters", "part_revisions",
        "part_iterations", "binary_resources", "geometries",
        "part_usage_links", "cad_instances",
    }
    actual = set(Base.metadata.tables.keys())
    assert expected <= actual, f"缺表: {expected - actual}"
```

- [ ] **Step 2: 跑测试确认通过（模型已全部就位）**

Run: `python -m pytest tests/test_models.py::test_metadata_has_all_nine_tables -v`
Expected: PASS

- [ ] **Step 3: 提交**

```bash
git add backend/tests/test_models.py
git commit -m "test(part-api): 校验 9 张核心表全部注册到 metadata"
```

---

### Task 7: Alembic 初始化与首版迁移（对真实 PostgreSQL）

**Files:**
- Create: `backend/alembic.ini`
- Create: `backend/migrations/env.py`
- Create: `backend/migrations/script.py.mako`（init 生成）
- Create: `backend/migrations/versions/0001_initial_schema.py`（autogenerate）

> 本任务需要可连的 PostgreSQL。先启动：`docker compose up -d db`（宿主 5435）。本地运行 alembic 时设 `DATABASE_URL=postgresql://plm:plmpass@localhost:5435/plm_unified`。

- [ ] **Step 1: 初始化 alembic 骨架**

Run（在 `backend/`）：
```bash
alembic init -t generic migrations
```
Expected: 生成 `alembic.ini`、`migrations/env.py`、`migrations/script.py.mako`、空 `migrations/versions/`。

- [ ] **Step 2: 改 alembic.ini —— 移除硬编码 URL**

编辑 `backend/alembic.ini`，将 `sqlalchemy.url = driver://...` 一行改为空（留 env.py 注入）：
```ini
sqlalchemy.url =
```

- [ ] **Step 3: 改 env.py —— 接入 Base.metadata 与 DATABASE_URL**

把 `backend/migrations/env.py` 中 `target_metadata = None` 一段替换为：
```python
import os
from app.database import Base
import app.models  # noqa: F401  注册全部模型

target_metadata = Base.metadata

# 用环境变量覆盖 alembic.ini 的空 URL
config.set_main_option(
    "sqlalchemy.url",
    os.getenv("DATABASE_URL", "postgresql://plm:plmpass@localhost:5435/plm_unified"),
)
```
> 确保 `backend/` 在 `sys.path`：alembic 默认从 ini 所在目录运行，`from app...` 可直接导入。若报 ModuleNotFound，在 env.py 顶部加 `import sys, os; sys.path.insert(0, os.getcwd())`。

- [ ] **Step 4: 生成首版迁移**

Run：
```bash
DATABASE_URL=postgresql://plm:plmpass@localhost:5435/plm_unified \
  alembic revision --autogenerate -m "initial schema" --rev-id 0001_initial_schema
```
Expected: 生成 `migrations/versions/0001_initial_schema.py`，`upgrade()` 含 9 个 `op.create_table`。

- [ ] **Step 5: 人工校订迁移**

打开 `0001_initial_schema.py` 核对：
- [ ] 9 张表齐全，外键 `ondelete` 与模型一致（CASCADE/RESTRICT/SET NULL）
- [ ] `uq_part_master_ws_number`、`uq_part_revision_master_version`、`uq_part_iteration_revision_iter`、`binary_resources.full_name` 唯一约束在
- [ ] `ck_part_revision_status`、`ck_part_iteration_positive`、`ck_cad_instance_rotation_type` CHECK 在
- [ ] `"order"` 列已正确加引号
- [ ] data-model.md §五 的 11 条索引——autogenerate 不会生成"查询用"索引（只生成约束隐含索引）。**手动在 `upgrade()` 末尾补**：
```python
    op.create_index("idx_part_masters_workspace", "part_masters", ["workspace_id"])
    op.create_index("idx_part_masters_number", "part_masters", ["number"])
    op.create_index("idx_part_revisions_master", "part_revisions", ["part_master_id"])
    op.create_index("idx_part_revisions_checkout", "part_revisions", ["checkout_user_id"])
    op.create_index("idx_part_revisions_status", "part_revisions", ["status"])
    op.create_index("idx_part_iterations_revision", "part_iterations", ["part_revision_id"])
    op.create_index("idx_geometries_iteration", "geometries", ["iteration_id"])
    op.create_index("idx_part_usage_links_parent", "part_usage_links", ["parent_iteration_id"])
    op.create_index("idx_part_usage_links_component", "part_usage_links", ["component_master_id"])
    op.create_index("idx_cad_instances_usage_link", "cad_instances", ["usage_link_id"])
```
（并在 `downgrade()` 顶部对应 `op.drop_index(...)`。`idx_binary_resources_fullname` 已由 unique 约束覆盖，无需重复。）

- [ ] **Step 6: 追加默认 workspace 种子**

在 `0001_initial_schema.py` 的 `upgrade()` 末尾追加（供 users.workspace_id 引用；admin 用户留待 1.5 认证计划）：
```python
    import uuid
    op.execute(
        "INSERT INTO workspaces (id, name, description, created_at, updated_at) "
        f"VALUES ('{uuid.uuid4()}', 'default', '默认工作空间', now(), now())"
    )
```

- [ ] **Step 7: 应用并验证 upgrade**

Run：
```bash
DATABASE_URL=postgresql://plm:plmpass@localhost:5435/plm_unified alembic upgrade head
DATABASE_URL=postgresql://plm:plmpass@localhost:5435/plm_unified alembic current
```
Expected: `0001_initial_schema (head)`；连库 `\dt` 见 9 张表 + 索引。

- [ ] **Step 8: 验证 downgrade 可回滚**

Run：
```bash
DATABASE_URL=postgresql://plm:plmpass@localhost:5435/plm_unified alembic downgrade base
DATABASE_URL=postgresql://plm:plmpass@localhost:5435/plm_unified alembic upgrade head
```
Expected: 先清空 9 表再重建，无报错。

- [ ] **Step 9: 提交**

```bash
git add backend/alembic.ini backend/migrations/
git commit -m "feat(part-api): 添加 Alembic 首版迁移（9 表+索引+默认工作空间）"
```

---

## Self-Review（已执行）

- **Spec 覆盖**：m1-execution-plan §4.2 的产出文件清单逐项对应 Task 1–7；9 表、UUID 应用侧、VARCHAR+CHECK 枚举、DATABASE_URL、autogenerate env.py、默认 workspace 种子均有任务。索引补齐在 Task 7 Step 5。
- **占位符**：无 TBD；每个代码步给出完整代码与确切命令/预期。
- **类型一致**：模型属性名（`workspace_id`/`checkout_user_id`/`rotation_type`/`order`）在测试与迁移校订步骤中一致引用；表名集合在 Task 6 与 Task 7 校验项一致。
- **已知约束**：Task 3/4 存在 binary 表先于其测试创建的次序耦合，已在 Task 3 Step 5 显式说明合并建模、分次写测试的执行顺序。

## 后续（不在本计划内）

- **任务 1.5 JWT 认证**：另起计划，依赖本计划交付的 `User`/`Workspace` 与默认 workspace；含 admin 种子用户、passlib/bcrypt 选型与锁版本、`JWT_SECRET` 强度修复。
- **任务 1.6/1.7（A 主写）**：CRUD 与签入签出，import 本计划冻结的模型。
