# myPDM 全量功能迁移至 plm-unified 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 myPDM 的全部业务模块（用户/文档/BOM/ECR/ECO/构型/库存/项目/仪表盘/自定义字段/日志/附件）迁移至 plm-unified 后端，替换前端 mock 数据为真实数据库。

**Architecture:** 从 myPDM 照搬 models/routers/schemas 到 plm-unified 的 `backend/app/` 目录，批量替换 FK 引用（component_id → part_master_id）。Router 挂载到 main.py。前端关闭 `VITE_USE_MOCK`，axios 直连后端 API。

**Tech Stack:** FastAPI + SQLAlchemy 2.0 + PostgreSQL 15 + Alembic + Pydantic 2.x + JWT (python-jose)

**Source repo:** `D:\OpenCode\myPDM`
**Target repo:** `D:\OpenCode\plm-unified`
**Working branch:** `feat/m3-viewer-lod`

---

## File Structure (Target)

```
backend/app/
├── models/
│   ├── __init__.py          (修改: 新增模块导入)
│   ├── mixins.py            (已有)
│   ├── workspace.py         (已有)
│   ├── user.py              (修改: 补 department/phone)
│   ├── part.py              (已有 M1)
│   ├── assembly.py          (已有 M2)
│   ├── binary.py            (已有 M2)
│   ├── models_document.py   (新增: 图文档)
│   ├── models_ecr.py        (新增: ECR)
│   ├── models_eco.py        (新增: ECO)
│   ├── models_configuration.py (新增: 构型)
│   ├── models_inventory.py  (新增: 库存)
│   └── models_project.py    (新增: 项目)
├── schemas/
│   ├── part.py              (已有 M1)
│   ├── assembly.py          (已有 M2)
│   ├── document.py          (新增)
│   ├── ecr.py               (新增)
│   ├── eco.py               (新增)
│   ├── configuration.py     (新增)
│   ├── inventory.py         (新增)
│   ├── project.py           (新增)
│   ├── user.py              (新增)
│   ├── custom_field.py      (新增)
│   ├── dashboard.py         (新增)
│   └── common.py            (新增: 通用 schema 工具)
├── routers/
│   ├── auth.py              (已有 M1)
│   ├── parts.py             (已有 M1)
│   ├── iterations.py        (已有 M2)
│   ├── conversion_compat.py (已有 M2)
│   ├── documents.py         (新增)
│   ├── bom.py               (新增: 适配 part_usage_links)
│   ├── users.py             (新增)
│   ├── user_groups.py       (新增)
│   ├── ecrs.py              (新增)
│   ├── ecos.py              (新增)
│   ├── configuration.py     (新增)
│   ├── inventory.py         (新增)
│   ├── projects.py          (新增)
│   ├── dashboard.py         (新增)
│   ├── custom_fields.py     (新增)
│   ├── logs.py              (新增)
│   ├── admin.py             (新增)
│   ├── attachments_v2.py    (新增)
│   └── sync.py              (新增)
├── crud/
│   ├── part.py              (已有 M1)
│   ├── assembly.py          (已有 M2)
│   ├── conversion.py        (已有 M2)
│   ├── document.py          (新增)
│   ├── ecr.py               (新增)
│   ├── eco.py               (新增)
│   ├── configuration.py     (新增)
│   ├── inventory.py         (新增)
│   └── project.py           (新增)
├── core/
│   ├── config.py            (修改: 补配置项)
│   ├── security.py          (已有)
│   └── permissions.py       (新增: 权限校验)
├── main.py                  (修改: 挂载新 router)
└── database.py              (已有)
migrations/versions/
├── 0004_extend_users.py     (新增)
├── 0005_documents.py         (新增)
├── 0006_ecr_eco.py           (新增)
├── 0007_configuration.py     (新增)
├── 0008_inventory.py         (新增)
└── 0009_project.py           (新增)
frontend/
├── .env                     (修改: 关闭 VITE_USE_MOCK)
└── src/
    └── services/
        └── api.ts           (修改: 切换真实 API)
permissions/
└── permissions.json         (新增: 从 myPDM 复制)
```

---

## Phase 0: 基础设施对齐

### Task 0.1: 复制权限配置

**Files:**
- Create: `backend/permissions/permissions.json`
- Create: `backend/app/core/permissions.py`

- [ ] **Step 1: 复制权限 JSON**

```bash
Copy-Item "D:\OpenCode\myPDM\permissions\permissions.json" "D:\OpenCode\plm-unified\backend\permissions\permissions.json"
```

- [ ] **Step 2: 编写权限校验依赖**

创建 `backend/app/core/permissions.py`:

```python
"""权限矩阵校验。从 permissions/permissions.json 加载。"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from fastapi import Depends, HTTPException, status

from app.models import User
from app.routers.auth import get_current_active_user

_permissions: dict[str, list[str]] = {}

def _load_permissions() -> dict[str, list[str]]:
    path = Path(__file__).parent.parent.parent / "permissions" / "permissions.json"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def require_permission(perm: str):
    """依赖注入：校验当前用户是否拥有指定权限。"""
    async def _check(current_user: User = Depends(get_current_active_user)):
        if not _permissions:
            _permissions.update(_load_permissions())
        allowed = _permissions.get(perm, [])
        if current_user.role not in allowed and "admin" not in current_user.role:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"缺少权限: {perm}")
        return current_user
    return _check
```

- [ ] **Step 3: 提交**

```bash
git add backend/permissions/permissions.json backend/app/core/permissions.py
git commit -m "feat(phase0): 复制 myPDM 权限配置 + 权限校验依赖"
```

---

### Task 0.2: 扩展 users 表补字段

**Files:**
- Create: `backend/migrations/versions/0004_extend_users.py`
- Modify: `backend/app/models/user.py`

- [ ] **Step 1: 修改 User 模型**

在 `backend/app/models/user.py` 的 `status` 字段后添加:

```python
    department = Column(String(128), nullable=True)
    phone = Column(String(32), nullable=True)
```

- [ ] **Step 2: 生成 Alembic 迁移**

```bash
$env:DATABASE_URL = "postgresql://plm:plmpass@localhost:5435/plm_unified"
$env:JWT_SECRET = "dev-only-secret-change-me-please-32chars"
alembic revision --autogenerate -m "extend users with department/phone"
```

- [ ] **Step 3: 执行迁移**

```bash
alembic upgrade head
```

验证：

```bash
docker exec plm_db psql -U plm -d plm_unified -c "\d users"
```

应显示 `department` 和 `phone` 列。

- [ ] **Step 4: 提交**

```bash
git add backend/app/models/user.py backend/migrations/versions/0004_*.py
git commit -m "feat(phase0): users 表补 department/phone 字段"
```

---

### Task 0.3: 更新 config.py 和 main.py 框架

**Files:**
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/main.py`

- [ ] **Step 1: 补 config 缺失项**

在 `backend/app/core/config.py` 的 `Settings` 类中添加 myPDM 需要的配置:

```python
    redis_url: str = "redis://redis:6379"
    uploads_path: str = "/uploads"
    cors_origins: list[str] = ["https://localhost:8080", "http://localhost:8080"]
```

- [ ] **Step 2: 更新 main.py 挂载框架**

在 `backend/app/main.py` 的 `# 路由挂载` 区域，将现有的 3 行 router 注释替换为完整版（为后续 Phase 占位，实际路由在各 Phase 中逐步激活）:

```python
# Phase 0: 已有路由
app.include_router(auth.router, prefix="/api")
app.include_router(parts_router)
app.include_router(iterations_router)
app.include_router(conversion_compat_router, prefix="/api")

# Phase 1+: 逐 Phase 取消注释
# from app.routers.documents import router as documents_router
# app.include_router(documents_router, prefix="/api")
# from app.routers.users import router as users_router
# app.include_router(users_router, prefix="/api")
# from app.routers.user_groups import router as user_groups_router
# app.include_router(user_groups_router, prefix="/api")
# from app.routers.bom import router as bom_router
# app.include_router(bom_router, prefix="/api")
# from app.routers.ecrs import router as ecrs_router
# app.include_router(ecrs_router, prefix="/api")
# from app.routers.ecos import router as ecos_router
# app.include_router(ecos_router, prefix="/api")
# from app.routers.configuration import router as configuration_router
# app.include_router(configuration_router, prefix="/api")
# from app.routers.inventory import router as inventory_router
# app.include_router(inventory_router, prefix="/api")
# from app.routers.projects import router as projects_router
# app.include_router(projects_router, prefix="/api")
# from app.routers.dashboard import router as dashboard_router
# app.include_router(dashboard_router, prefix="/api")
# from app.routers.custom_fields import router as custom_fields_router
# app.include_router(custom_fields_router, prefix="/api")
# from app.routers.logs import router as logs_router
# app.include_router(logs_router, prefix="/api")
# from app.routers.admin import router as admin_router
# app.include_router(admin_router, prefix="/api")
# from app.routers.attachments_v2 import router as attachments_router
# app.include_router(attachments_router, prefix="/api")
# from app.routers.sync import router as sync_router
# app.include_router(sync_router, prefix="/api")
```

- [ ] **Step 3: 提交**

```bash
git add backend/app/core/config.py backend/app/main.py
git commit -m "feat(phase0): 补 config + main.py 路由挂载框架"
```

---

## Phase 1: 实体层（用户 CRUD + 图文档 CRUD + 附件）

### Task 1.1: 用户管理 CRUD

**Files:**
- Create: `backend/app/schemas/user.py`
- Create: `backend/app/routers/users.py`

- [ ] **Step 1: 从 myPDM 复制并适配**

```bash
Copy-Item "D:\OpenCode\myPDM\backend\app\routers\users.py" "D:\OpenCode\plm-unified\backend\app\routers\users.py"
```

在复制的 `users.py` 中修改 import 路径：

```python
# 原: from app.database import get_db
# → 已经是统一路径，无需改
# 原: from app.models import User
# → 确认 plm-unified 的 models/__init__.py 导出了 User

# 检查并修正 model 引用
# from app.models.user import User → from app.models import User
```

- [ ] **Step 2: 编写 User schema**

创建 `backend/app/schemas/user.py`:

```python
"""用户相关 Pydantic schema。"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


def _to_camel(s: str) -> str:
    parts = s.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


class UserCreate(BaseModel):
    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True)

    username: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=6, max_length=128)
    real_name: str = Field(..., min_length=1, max_length=64)
    role: str = Field("engineer", max_length=32)
    department: Optional[str] = Field(None, max_length=128)
    phone: Optional[str] = Field(None, max_length=32)
    workspace_id: Optional[uuid.UUID] = None


class UserUpdate(BaseModel):
    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True)

    username: Optional[str] = Field(None, min_length=1, max_length=64)
    real_name: Optional[str] = Field(None, min_length=1, max_length=64)
    role: Optional[str] = Field(None, max_length=32)
    department: Optional[str] = Field(None, max_length=128)
    phone: Optional[str] = Field(None, max_length=32)
    status: Optional[str] = Field(None, max_length=32)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, alias_generator=_to_camel, populate_by_name=True)

    id: uuid.UUID
    workspace_id: Optional[uuid.UUID] = None
    username: str
    real_name: str
    role: str
    department: Optional[str] = None
    phone: Optional[str] = None
    status: str
    created_at: datetime
    updated_at: datetime
```

- [ ] **Step 3: 激活路由**

在 `backend/app/main.py` 中取消注释 Phase 1 路由:

```python
from app.routers.users import router as users_router
app.include_router(users_router, prefix="/api")
```

- [ ] **Step 4: 验证端点**

```bash
# 重启后端容器
docker compose restart backend

# 测试用户列表（需要 admin token）
Invoke-RestMethod -Uri "http://localhost:8010/api/users/" -Method Get
```

预期返回 admin 用户列表。

- [ ] **Step 5: 提交**

```bash
git add backend/app/schemas/user.py backend/app/routers/users.py backend/app/main.py
git commit -m "feat(phase1): 用户管理 CRUD（照搬 myPDM + camelCase schema）"
```

---

### Task 1.2: 用户组 CRUD

**Files:**
- Create: `backend/app/routers/user_groups.py`

- [ ] **Step 1: 复制并适配**

```bash
Copy-Item "D:\OpenCode\myPDM\backend\app\routers\user_groups.py" "D:\OpenCode\plm-unified\backend\app\routers\user_groups.py"
```

检查 import 路径，修正：
- `from app.models import UserGroup, User, user_group_members` → 确保 model 在 plm-unified 中存在

- [ ] **Step 2: 确认 UserGroup 模型存在**

检查 myPDM 的 `backend/app/models.py` 中 UserGroup 定义。如果在 models.py 中，需要将该类单独提取到 plm-unified 的 `backend/app/models/user_groups.py`。如果 myPDM 模型是分散的，创建对应的 model 文件。

创建 `backend/app/models/user_groups.py`:

```python
"""用户组模型。"""
import uuid
from sqlalchemy import Column, String, Text, ForeignKey, Table, Uuid
from app.database import Base
from app.models.mixins import TimestampMixin


user_group_members = Table(
    "user_group_members",
    Base.metadata,
    Column("user_id", Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("group_id", Uuid(as_uuid=True), ForeignKey("user_groups.id", ondelete="CASCADE"), primary_key=True),
)


class UserGroup(Base, TimestampMixin):
    __tablename__ = "user_groups"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(64), unique=True, nullable=False)
    description = Column(Text, nullable=True)
```

- [ ] **Step 3: 生成迁移并执行**

```bash
alembic revision --autogenerate -m "add user_groups table"
alembic upgrade head
```

- [ ] **Step 4: 更新 models/__init__.py**

在 `backend/app/models/__init__.py` 中添加:

```python
from app.models.user_groups import UserGroup, user_group_members
```

并在 `__all__` 列表中加入 `"UserGroup"`。

- [ ] **Step 5: 挂载路由并测试**

```python
# main.py
from app.routers.user_groups import router as user_groups_router
app.include_router(user_groups_router, prefix="/api")
```

- [ ] **Step 6: 提交**

```bash
git add backend/app/models/user_groups.py backend/app/models/__init__.py backend/app/routers/user_groups.py backend/app/main.py backend/migrations/versions/0005_*.py
git commit -m "feat(phase1): 用户组 CRUD"
```

---

### Task 1.3: 图文档 CRUD

**Files:**
- Create: `backend/app/models/models_document.py`
- Create: `backend/app/schemas/document.py`
- Create: `backend/app/routers/documents.py`
- Create: `backend/app/crud/document.py`
- Create: `backend/migrations/versions/0006_documents.py`

- [ ] **Step 1: 分析 myPDM 文档模型**

查看 myPDM 的 `backend/app/models.py` 中 Document / DocumentAttachment 的完整定义。

- [ ] **Step 2: 创建 plm-unified 文档模型**

创建 `backend/app/models/models_document.py`:

```python
"""图文档模型。从 myPDM 照搬，component_id 改为 part_master_id。"""
import uuid
from sqlalchemy import Column, String, Text, Uuid, ForeignKey, Integer, BigInteger, JSON, func, DateTime
from app.database import Base
from app.models.mixins import TimestampMixin, SoftDeleteMixin


class Document(Base, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "documents"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code = Column(String(64), nullable=False)
    name = Column(String(255), nullable=False)
    version = Column(String(10), nullable=False, default="A")
    status = Column(String(32), nullable=False, default="draft")
    remark = Column(Text, nullable=True)
    file_name = Column(String(500), nullable=True)
    file_id = Column(Uuid(as_uuid=True), ForeignKey("document_attachments.id", ondelete="SET NULL"), nullable=True)
    revisions = Column(JSON, nullable=True, default=list)
    revision_parent_id = Column(Uuid(as_uuid=True), ForeignKey("documents.id", ondelete="SET NULL"), nullable=True)
    creator_id = Column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)


class DocumentAttachment(Base, TimestampMixin):
    __tablename__ = "document_attachments"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(Uuid(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    file_name = Column(String(500), nullable=False)
    file_size = Column(BigInteger, nullable=False, default=0)
    file_path = Column(String(1000), nullable=False)
    file_hash = Column(String(64), nullable=True)


class DocumentLink(Base):
    """文档-零件关联（原 myPDM document_links JSONB 改为独立表）。"""
    __tablename__ = "document_links"

    id = Column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(Uuid(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False)
    entity_type = Column(String(32), nullable=False)  # "part" / "configuration_item" / "eco"
    entity_id = Column(Uuid(as_uuid=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
```

注意：myPDM 用 JSONB `document_links` 字段存文档-实体的关联，这里改为独立表 `document_links` 以提高查询性能。

- [ ] **Step 3: 创建 schemas**

创建 `backend/app/schemas/document.py`（照搬 myPDM 的 Document schema，加 camelCase alias）:

```python
"""图文档 Pydantic schema。"""
from __future__ import annotations
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


def _to_camel(s: str) -> str:
    parts = s.split("_")
    return parts[0] + "".join(p.capitalize() for p in parts[1:])


class DocumentCreate(BaseModel):
    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True)
    code: str = Field(..., min_length=1, max_length=64)
    name: str = Field(..., min_length=1, max_length=255)
    remark: Optional[str] = None


class DocumentUpdate(BaseModel):
    model_config = ConfigDict(alias_generator=_to_camel, populate_by_name=True)
    code: Optional[str] = None
    name: Optional[str] = None
    status: Optional[str] = None
    remark: Optional[str] = None


class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, alias_generator=_to_camel, populate_by_name=True)
    id: uuid.UUID
    code: str
    name: str
    version: str
    status: str
    remark: Optional[str] = None
    file_name: Optional[str] = None
    file_id: Optional[uuid.UUID] = None
    creator_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
```

- [ ] **Step 4: 创建 Router（照搬 myPDM + 路径修正）**

```bash
Copy-Item "D:\OpenCode\myPDM\backend\app\routers\documents.py" "D:\OpenCode\plm-unified\backend\app\routers\documents.py"
```

修正 import:
- `from app.models import Document, DocumentAttachment` → `from app.models.models_document import Document, DocumentAttachment, DocumentLink`
- 如果 myPDM 的 documents router 引用了 `check_component_exists` 之类函数，改为引用 PartMaster

- [ ] **Step 5: 生成迁移并执行**

```bash
alembic revision --autogenerate -m "add documents tables"
alembic upgrade head
```

- [ ] **Step 6: 更新 models/__init__.py**

```python
from app.models.models_document import Document, DocumentAttachment, DocumentLink
```

- [ ] **Step 7: 挂载路由**

```python
# main.py
from app.routers.documents import router as documents_router
app.include_router(documents_router, prefix="/api")
```

- [ ] **Step 8: 重启并测试**

```bash
docker compose restart backend
# 测试创建文档
$headers = @{Authorization="Bearer $token"}
Invoke-RestMethod -Uri "http://localhost:8010/api/documents/" -Method Get -Headers $headers
```

- [ ] **Step 9: 提交**

```bash
git add backend/app/models/models_document.py backend/app/schemas/document.py backend/app/routers/documents.py backend/app/crud/document.py backend/migrations/versions/0006_*.py backend/app/models/__init__.py backend/app/main.py
git commit -m "feat(phase1): 图文档 CRUD（照搬 myPDM + FK 适配 PartMaster）"
```

---

### Task 1.4: 附件上传下载（attachments_v2）

**Files:**
- Create: `backend/app/routers/attachments_v2.py`

- [ ] **Step 1: 从 myPDM 照搬附件路由**

```bash
Copy-Item "D:\OpenCode\myPDM\backend\app\routers\attachments_v2.py" "D:\OpenCode\plm-unified\backend\app\routers\attachments_v2.py"
```

检查并修正：
- import 路径适配 plm-unified
- 文件上传目录指向 `settings.uploads_path`
- media token 签发使用 `app.core.security.create_access_token`

- [ ] **Step 2: 确保依赖已安装**

检查 myPDM 的附件模块依赖了哪些额外包（`aiofiles`, `rarfile`, `py7zr` 等），安装到 plm-unified:

```bash
pip install aiofiles rarfile py7zr
```

更新 `backend/requirements.txt` 添加缺失的依赖。

- [ ] **Step 3: 挂载路由并测试**

```python
# main.py
from app.routers.attachments_v2 import router as attachments_router
app.include_router(attachments_router, prefix="/api")
```

- [ ] **Step 4: 提交**

```bash
git add backend/app/routers/attachments_v2.py backend/app/main.py backend/requirements.txt
git commit -m "feat(phase1): 附件上传下载（照搬 myPDM attachments_v2）"
```

---

## Phase 2: 关系层（BOM + 文档链接）

### Task 2.1: BOM 路由适配

**Files:**
- Create: `backend/app/routers/bom.py`

myPDM 的 BOM 模块基于 `bom_items` 表（parent_type/parent_id/child_type/child_id），plm-unified 使用 `part_usage_links` + `cad_instances`。关键改动：

| myPDM BOM 端点 | plm-unified 适配方式 |
|---------------|-------------------|
| `GET /bom/tree/{type}/{id}` | `GET /api/parts/{num}/{ver}/instances` (已有) + 包装 BOM 树格式 |
| `GET /bom/items/all` | 查询 `part_usage_links` 表全量 |
| `GET /bom/references/{type}/{id}` | 查 `part_usage_links` + `document_links` |
| `POST /bom/items` | `PUT /api/parts/{num}/{ver}/iterations/{iter}` (已有) |
| `DELETE /bom/items/{id}` | 删除 `part_usage_links` 行 |
| `POST /bom/compare` | 基于 instances API 比较两个装配体的实例列表 |
| `GET /bom/trace/{type}/{id}` | 递归反查 part_usage_links.component_master_id |
| `GET /bom/export/{type}/{id}` | 遍历 BOM 树输出 CSV |

- [ ] **Step 1: 创建 BOM router**

创建 `backend/app/routers/bom.py`，实现上述 8 个端点，底层数据源改为 `part_usage_links` / `cad_instances`:

```python
"""BOM 路由（适配 part_usage_links + cad_instances）。"""
from __future__ import annotations
import csv
import io
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.crud.assembly import compute_instances
from app.database import get_db
from app.models import User
from app.models.assembly import PartUsageLink, CADInstance
from app.models.part import PartMaster, PartRevision, PartIteration
from app.routers.auth import get_current_active_user

router = APIRouter(prefix="/api/bom", tags=["BOM"])


@router.get("/items/all")
def get_all_bom_items(
    workspace_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """返回所有 BOM 关系（适配 part_usage_links）。"""
    links = (
        db.query(PartUsageLink)
        .join(PartIteration, PartUsageLink.parent_iteration_id == PartIteration.id)
        .join(PartRevision, PartIteration.part_revision_id == PartRevision.id)
        .join(PartMaster, PartRevision.part_master_id == PartMaster.id)
        .filter(PartMaster.workspace_id == workspace_id, PartMaster.deleted_at.is_(None))
        .all()
    )
    result = []
    for link in links:
        child = db.get(PartMaster, link.component_master_id)
        result.append({
            "id": str(link.id),
            "parent_type": "part",
            "parent_id": str(link.parent_iteration_id),
            "child_type": "part",
            "child_id": str(link.component_master_id),
            "child_code": child.number if child else "?",
            "child_name": child.name if child else "?",
            "quantity": link.amount,
            "unit": link.unit,
            "order": link.order,
            "optional": link.optional,
        })
    return result


@router.get("/tree/{entity_type}/{entity_id}")
def get_bom_tree(
    entity_type: str,
    entity_id: str,
    workspace_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """BOM 树：基于 part_usage_links 递归构建。"""
    root_master = db.get(PartMaster, uuid.UUID(entity_id))
    if not root_master:
        raise HTTPException(status_code=404, detail="零件不存在")
    return _build_bom_tree(db, root_master)


def _build_bom_tree(db: Session, master: PartMaster, visited: set | None = None) -> dict:
    if visited is None:
        visited = set()
    key = str(master.id)
    if key in visited:
        return {"id": key, "code": master.number, "name": master.name, "children": [], "_circular": True}
    visited.add(key)

    revision = (
        db.query(PartRevision)
        .filter(PartRevision.part_master_id == master.id, PartRevision.deleted_at.is_(None))
        .order_by(PartRevision.version.desc())
        .first()
    )
    if not revision:
        return {"id": key, "code": master.number, "name": master.name, "children": []}

    iteration = (
        db.query(PartIteration)
        .filter(PartIteration.part_revision_id == revision.id, PartIteration.check_in_date.is_not(None))
        .order_by(PartIteration.iteration.desc())
        .first()
    )
    if not iteration:
        return {"id": key, "code": master.number, "name": master.name, "children": []}

    links = (
        db.query(PartUsageLink)
        .filter(PartUsageLink.parent_iteration_id == iteration.id)
        .order_by(PartUsageLink.order)
        .all()
    )

    children = []
    for link in links:
        child_master = db.get(PartMaster, link.component_master_id)
        if child_master:
            child_tree = _build_bom_tree(db, child_master, visited.copy())
            child_tree["quantity"] = link.amount
            child_tree["unit"] = link.unit
            child_tree["order"] = link.order
            children.append(child_tree)

    return {"id": key, "code": master.number, "name": master.name, "children": children}


@router.get("/trace/{entity_type}/{entity_id}")
def trace_where_used(
    entity_type: str,
    entity_id: str,
    workspace_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """反查：哪些装配体使用了指定零件（递归向上）。"""
    component_id = uuid.UUID(entity_id)
    links = db.query(PartUsageLink).filter(PartUsageLink.component_master_id == component_id).all()
    result = []
    for link in links:
        iteration = db.get(PartIteration, link.parent_iteration_id)
        if not iteration:
            continue
        revision = db.get(PartRevision, iteration.part_revision_id)
        if not revision:
            continue
        parent_master = db.get(PartMaster, revision.part_master_id)
        if not parent_master:
            continue
        result.append({
            "parent_code": parent_master.number,
            "parent_name": parent_master.name,
            "parent_version": revision.version,
            "quantity": link.amount,
        })
    return result


@router.get("/export/{entity_type}/{entity_id}")
def export_bom_csv(
    entity_type: str,
    entity_id: str,
    workspace_id: uuid.UUID = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_active_user),
):
    """导出 BOM 为 CSV。"""
    from fastapi.responses import StreamingResponse
    master = db.get(PartMaster, uuid.UUID(entity_id))
    if not master:
        raise HTTPException(status_code=404)
    tree = _build_bom_tree(db, master)

    def _flatten(node, level=0):
        rows = []
        rows.append([node.get("code", ""), node.get("name", ""), level, node.get("quantity", ""), node.get("unit", "")])
        for child in node.get("children", []):
            rows.extend(_flatten(child, level + 1))
        return rows

    rows = _flatten(tree)
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["编号", "名称", "层级", "数量", "单位"])
    writer.writerows(rows)
    output.seek(0)
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f"attachment; filename={master.number}_BOM.csv"})
```

- [ ] **Step 2: 挂载路由**

```python
# main.py
from app.routers.bom import router as bom_router
app.include_router(bom_router, prefix="/api")
```

- [ ] **Step 3: 测试 BOM 端点**

```bash
docker compose restart backend
# 创建装配体 + 子零件 + 写入 BOM（用已有 M2 API）
# 然后测试 GET /api/bom/tree/part/{id}
```

- [ ] **Step 4: 提交**

```bash
git add backend/app/routers/bom.py backend/app/main.py
git commit -m "feat(phase2): BOM 路由（适配 part_usage_links）"
```

---

## Phase 3: 流程层（ECR + ECO）

ECR 和 ECO 是 myPDM 最复杂的两个模块，涉及审批流状态机。

### Task 3.1: ECR 模块

**Files:**
- Create: `backend/app/models/models_ecr.py`
- Create: `backend/app/schemas/ecr.py`
- Create: `backend/app/routers/ecrs.py`
- Create: `backend/app/crud/ecr.py`
- Create: `backend/migrations/versions/0007_ecr_eco.py`

- [ ] **Step 1: 创建 ECR 模型（照搬 myPDM + FK 修正）**

创建 `backend/app/models/models_ecr.py`，照搬 myPDM `models_ecr.py`，唯一改动：
- `ECRAffectedItem.entity_id` FK 注释去掉 `→ components` 限制，改为通用 UUID 引用（指向 PartMaster/Document）

- [ ] **Step 2: 创建 Schema + Router**

照搬 myPDM 的 `routers/ecrs.py` 和 Pydantic schema。

- [ ] **Step 3: 适配状态机**

myPDM ECR 状态机：draft → submitted → reviewing → approved/rejected/returned → closed

plm-unified 已有 `get_current_active_user` 认证依赖，路由中替换原 myPDM 的认证调用。

- [ ] **Step 4: 生成迁移执行**

```bash
alembic revision --autogenerate -m "add ECR tables"
alembic upgrade head
```

- [ ] **Step 5: 挂载路由并提交**

```bash
git add backend/app/models/models_ecr.py backend/app/schemas/ecr.py backend/app/routers/ecrs.py backend/app/crud/ecr.py backend/app/migrations/versions/0007_*.py backend/app/main.py
git commit -m "feat(phase3): ECR 模块（照搬 myPDM + FK 适配 PartMaster）"
```

---

### Task 3.2: ECO 模块

**Files:**
- Create: `backend/app/models/models_eco.py`
- Create: `backend/app/schemas/eco.py`
- Create: `backend/app/routers/ecos.py`
- Create: `backend/app/crud/eco.py`

- [ ] **Step 1: 创建 ECO 模型（照搬 myPDM + FK 修正）**

创建 `backend/app/models/models_eco.py`，照搬 myPDM `models_eco.py`:
- `ECOExecutionItem.entity_id` → PartMaster UUID
- `ECOExecutionItem.new_entity_id` → 新版本的 PartMaster UUID（版本升级后）
- `ECOExecutionItem.action` 保留 myPDM 5 种动作类型：`upgrade / release / freeze / revert / publish`

- [ ] **Step 2: 创建 Schema + Router**

照搬 myPDM 的 `routers/ecos.py`。

- [ ] **Step 3: 适配 PartMaster 状态机交互**

myPDM ECO 执行时调用的 `upgrade/release/freeze/revert` 需要映射到 plm-unified 的 PartMaster 操作：
- `upgrade` → 调用 plm-unified checkout → 修改 → checkin 流（如果未签出需先签出）
- `release` → 改 `part_revisions.status = 'RELEASED'`
- `freeze` → 改 `part_revisions.status = 'OBSOLETE'` 或设 check_in_date
- `revert` → 回滚到上一版本

这需要在 `backend/app/crud/eco.py` 中实现对 PartMaster 状态机的操作封装。

- [ ] **Step 4: 提交**

```bash
git add backend/app/models/models_eco.py backend/app/schemas/eco.py backend/app/routers/ecos.py backend/app/crud/eco.py backend/app/main.py
git commit -m "feat(phase3): ECO 模块（照搬 myPDM + 适配 PartMaster 状态机）"
```

---

## Phase 4: 构型 + 库存 + 项目

### Task 4.1: 构型管理

**Files:**
- Create: `backend/app/models/models_configuration.py`
- Create: `backend/app/schemas/configuration.py`
- Create: `backend/app/routers/configuration.py`
- Create: `backend/migrations/versions/0008_configuration.py`

照搬 myPDM `models_configuration.py` + `routers/configuration.py`，适配：
- `ConfigurationItemPart.part_id` → `part_master_id` (FK→part_masters)
- `ConfigurationItemChild.child_id` → 自引用 FK 不变

- [ ] **Step 1: 创建模型 schema router**
- [ ] **Step 2: 生成迁移执行**
- [ ] **Step 3: 挂载提交**

---

### Task 4.2: 库存管理

**Files:**
- Create: `backend/app/models/models_inventory.py`
- Create: `backend/app/schemas/inventory.py`
- Create: `backend/app/routers/inventory.py`
- Create: `backend/migrations/versions/0009_inventory.py`

照搬 myPDM `models_inventory.py` + `routers/inventory.py`，适配：
- `InventoryMaterial.ref_entity_id` 可指向 PartMaster UUID
- 库存单据的审批流依赖权限系统

- [ ] **Step 1: 创建模型 schema router**
- [ ] **Step 2: 生成迁移执行**
- [ ] **Step 3: 挂载提交**

---

### Task 4.3: 项目管理

**Files:**
- Create: `backend/app/models/models_project.py`
- Create: `backend/app/schemas/project.py`
- Create: `backend/app/routers/projects.py`
- Create: `backend/migrations/versions/0010_projects.py`

照搬 myPDM `models_project.py` + `routers/projects.py`（零 FK 适配，直接复制）。

- [ ] **Step 1: 创建模型 schema router**
- [ ] **Step 2: 生成迁移执行**
- [ ] **Step 3: 挂载提交**

---

## Phase 5: 支撑 + 前端切换

### Task 5.1: 仪表盘/看板

**Files:**
- Create: `backend/app/routers/dashboard.py`
- Create: `backend/migrations/versions/0011_dashboard.py`

照搬 myPDM dashboard 模块，适配 `entity_id` → PartMaster UUID。

---

### Task 5.2: 自定义字段

**Files:**
- Create: `backend/app/routers/custom_fields.py`
- Create: `backend/migrations/versions/0012_custom_fields.py`

照搬 myPDM 自定义字段模块（零 FK 适配）。

---

### Task 5.3: 操作日志 + 数据管理

**Files:**
- Create: `backend/app/routers/logs.py`
- Create: `backend/app/routers/admin.py`
- Create: `backend/migrations/versions/0013_logs.py`

照搬 myPDM logs + admin 模块（零 FK 适配）。

---

### Task 5.4: 前端关闭 Mock

**Files:**
- Modify: `frontend/.env`

- [ ] **Step 1: 修改 .env**

```
VITE_USE_MOCK=0
```

- [ ] **Step 2: 更新 axios 配置**

检查 `frontend/src/services/api.ts`，确保 mock adapter 不在 production/mock-off 模式下注入。

- [ ] **Step 3: 逐页验收**

依次打开每个前端页面，验证数据正确：
1. `/login` → `/dashboard` → `/board`
2. `/parts` → 检查零件列表/详情
3. `/documents` → 检查文档 CRUD
4. `/bom` → 检查 BOM 树/对比/反查
5. `/ec` → 检查 ECR + ECO
6. `/inventory` → 检查库存四个页面
7. `/projects` → 检查项目和甘特图
8. `/configuration` → 检查构型管理
9. `/users` → 检查用户管理
10. `/settings` → 检查自定义字段/日志/数据管理

- [ ] **Step 4: 提交**

```bash
git add frontend/.env frontend/src/services/api.ts
git commit -m "feat(phase5): 前端关闭 mock，切换真实 API"
```

---

## 附录：关键技术注意事项

### A. component_id → part_master_id 全局替换

在每个从 myPDM 复制的文件中执行：

```python
# 搜索替换模式
"component_id" → "part_master_id"
"Component" (model 类引用) → "PartMaster"
"component" (变量名) → 保持可读的上下文，如 "affected_part"
```

### B. 测试策略

每个 Phase 完成后运行：

```bash
$env:DATABASE_URL = "postgresql://plm:plmpass@localhost:5435/plm_unified"
pytest backend/tests/ -x -v
```

新增的模块测试参考 `backend/tests/test_m1_acceptance.py` 的模式：
- 使用 TestClient + SQLite 内存库
- 每个测试独立 DB session
- 覆盖 CRUD + 状态机 + 错误路径

### C. Docker 部署验证

每个 Phase 完成后：

```bash
docker compose up -d --build
docker ps  # 确认 6 个容器 Running
Invoke-RestMethod -Uri "http://localhost:8010/health"
```
