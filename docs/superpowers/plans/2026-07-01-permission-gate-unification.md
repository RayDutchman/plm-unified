# 权限门控统一 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 合并双套 require_permission 实现，消除 ECR/ECO 内联角色判断，补齐 sync 门控，统一所有 Router import 路径。

**Architecture:** `app/permissions/__init__.py` 成为唯一权限入口（含 admin 全局豁免），`app/core/permissions.py` 降级为 re-export 兼容层。所有非零部件 Router 统一 `from app.permissions import require_permission, enforce_object_policy`。

**Tech Stack:** Python FastAPI, SQLAlchemy, 项目已用的 app.permissions / app.core.permissions 模块

**Spec:** `docs/superpowers/specs/2026-07-01-permission-gate-unification.md`
**代码规范:** `docs/collaboration/milestones.md` — snake_case, 注释用中文, 提交格式 `type(scope): description`

---

### Task 1: 权限矩阵 — 新增 eco:approve 并重新生成

**Files:**
- Modify: `permissions/permissions.json`
- Modify: `backend/app/permissions/_generated.py` (regenerated)

- [ ] **Step 1: 在 permissions.json 中新增 eco:approve 条目**

在 `"eco:close"` 行后插入：
```json
"eco:approve": { "roles": ["admin", "engineer"], "object_policy": "eco_approver_or_admin" },
```

- [ ] **Step 2: 运行生成脚本**

```powershell
python tools/gen_permissions.py
```

- [ ] **Step 3: 验证 _generated.py 包含新条目**

```powershell
python -c "from app.permissions._generated import PERMISSIONS; print('eco:approve' in PERMISSIONS)"
```
Expected output: `True`

- [ ] **Step 4: Commit**

```bash
git add permissions/permissions.json backend/app/permissions/_generated.py
git commit -m "feat(permission): 新增 eco:approve 权限项并重新生成矩阵"
```

---

### Task 2: 策略 — 新增 eco_approver_or_admin 策略函数

**Files:**
- Modify: `backend/app/permissions/policies.py`

- [ ] **Step 1: 在 _eco_owner_or_admin 策略后添加新策略**

在 `_eco_owner_or_admin` 函数定义后（约 line 38），添加：

```python
@register_policy("eco_approver_or_admin")
def _eco_approver_or_admin(user, eco, *, reviewer_ids=None, **_):
    return _is_admin(user) or (reviewer_ids is not None and user.id in reviewer_ids)
```

- [ ] **Step 2: 验证策略注册成功**

```powershell
python -c "from app.permissions.policies import check_object_policy; print('eco_approver_or_admin registered')"
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/permissions/policies.py
git commit -m "feat(permission): 新增 eco_approver_or_admin 对象策略"
```

---

### Task 3: 模块 — __init__.py 增加 admin 全局豁免

**Files:**
- Modify: `backend/app/permissions/__init__.py`

- [ ] **Step 1: 重写 require_permission 增加 admin 豁免**

当前代码（第 13-22 行）：
```python
def require_permission(perm: str):
    if perm not in PERMISSIONS:
        raise KeyError(f"Unknown permission: {perm}")
    from fastapi import Depends, HTTPException
    from app.routers.auth import get_current_active_user

    async def checker(current_user: User = Depends(get_current_active_user)) -> User:
        if current_user.role not in PERMISSIONS[perm]:
            raise HTTPException(status_code=403, detail="权限不足")
        return current_user
    return checker
```

改为：
```python
def require_permission(perm: str):
    if perm not in PERMISSIONS:
        raise KeyError(f"Unknown permission: {perm}")
    from fastapi import Depends, HTTPException
    from app.routers.auth import get_current_active_user

    async def checker(current_user: User = Depends(get_current_active_user)) -> User:
        if current_user.role not in PERMISSIONS[perm] and current_user.role != "admin":
            raise HTTPException(status_code=403, detail="权限不足")
        return current_user
    return checker
```

- [ ] **Step 2: Commit**

```bash
git add backend/app/permissions/__init__.py
git commit -m "feat(permission): __init__ require_permission 增加 admin 全局豁免"
```

---

### Task 4: 模块 — core/permissions.py 改为兼容 re-export

**Files:**
- Modify: `backend/app/core/permissions.py`

- [ ] **Step 1: 替换文件内容为 re-export**

将整个文件内容替换为：
```python
"""兼容模块：请改用 app.permissions"""
from app.permissions import require_permission, has_permission, enforce_object_policy, register_policy, check_object_policy
```

- [ ] **Step 2: 验证 re-export 可用**

```powershell
python -c "from app.core.permissions import require_permission; print('re-export OK')"
```
Expected output: `re-export OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/core/permissions.py
git commit -m "refactor(permission): core/permissions.py 改为兼容 re-export"
```

---

### Task 5: Import 路径 — 批量替换所有非零部件 Router

**Files:**
- Modify: `backend/app/routers/users.py:9`
- Modify: `backend/app/routers/user_groups.py:9`
- Modify: `backend/app/routers/documents.py:20`
- Modify: `backend/app/routers/configuration.py:20`
- Modify: `backend/app/routers/custom_fields.py:10`
- Modify: `backend/app/routers/admin.py:9`
- Modify: `backend/app/routers/logs.py:8`
- Modify: `backend/app/routers/dashboard.py:11`
- Modify: `backend/app/routers/projects.py:14`
- Modify: `backend/app/routers/inventory.py:14-15`
- Modify: `backend/app/routers/attachments_v2.py:17`

- [ ] **Step 1: 替换 users.py 导入**

`D:\OpenCode\plm-unified\backend\app\routers\users.py` 第 9 行：
```
from app.core.permissions import require_permission
```
改为：
```
from app.permissions import require_permission
```

- [ ] **Step 2: 替换 user_groups.py 导入**

`D:\OpenCode\plm-unified\backend\app\routers\user_groups.py` 第 9 行，同上替换。

- [ ] **Step 3: 替换 documents.py 导入**

`D:\OpenCode\plm-unified\backend\app\routers\documents.py` 第 20 行，同上替换。

- [ ] **Step 4: 替换 configuration.py 导入**

`D:\OpenCode\plm-unified\backend\app\routers\configuration.py` 第 20 行，同上替换。

- [ ] **Step 5: 替换 custom_fields.py 导入**

`D:\OpenCode\plm-unified\backend\app\routers\custom_fields.py` 第 10 行，同上替换。

- [ ] **Step 6: 替换 admin.py 导入**

`D:\OpenCode\plm-unified\backend\app\routers\admin.py` 第 9 行，同上替换。

- [ ] **Step 7: 替换 logs.py 导入**

`D:\OpenCode\plm-unified\backend\app\routers\logs.py` 第 8 行，同上替换。

- [ ] **Step 8: 替换 dashboard.py 导入**

`D:\OpenCode\plm-unified\backend\app\routers\dashboard.py` 第 11 行：
```
from app.core.permissions import require_permission, enforce_object_policy
```
改为：
```
from app.permissions import require_permission, enforce_object_policy
```

- [ ] **Step 9: 替换 projects.py 导入**

`D:\OpenCode\plm-unified\backend\app\routers\projects.py` 第 14 行，同 Step 8 替换。

- [ ] **Step 10: 替换 inventory.py 导入**

`D:\OpenCode\plm-unified\backend\app\routers\inventory.py` 第 14-15 行：
```
from app.core.permissions import require_permission
from app.permissions.policies import enforce_object_policy
```
改为：
```
from app.permissions import require_permission, enforce_object_policy
```
（合并为一行，删除重复的 policies 导入）

- [ ] **Step 11: 替换 attachments_v2.py 导入**

`D:\OpenCode\plm-unified\backend\app\routers\attachments_v2.py` 第 17 行：
```
from ..permissions import require_permission, has_permission
```
改为：
```
from app.permissions import require_permission, has_permission
```

- [ ] **Step 12: 运行 Python 导入检查**

```powershell
python -c "from app.routers.users import router; from app.routers.user_groups import router; from app.routers.documents import router; from app.routers.configuration import router; from app.routers.custom_fields import router; from app.routers.admin import router; from app.routers.logs import router; from app.routers.dashboard import router; from app.routers.projects import router; from app.routers.inventory import router; from app.routers.attachments_v2 import router; print('All imports OK')"
```
Expected output: `All imports OK`

- [ ] **Step 13: Commit**

```bash
git add backend/app/routers/users.py backend/app/routers/user_groups.py backend/app/routers/documents.py backend/app/routers/configuration.py backend/app/routers/custom_fields.py backend/app/routers/admin.py backend/app/routers/logs.py backend/app/routers/dashboard.py backend/app/routers/projects.py backend/app/routers/inventory.py backend/app/routers/attachments_v2.py
git commit -m "refactor(permission): 统一非零部件 Router import 路径到 app.permissions"
```

---

### Task 6: ECR Router — 替换全部权限门控

**Files:**
- Modify: `backend/app/routers/ecrs.py`

- [ ] **Step 1: 替换导入**

第 13 行：
```
from app.routers.auth import get_current_active_user
```
改为：
```
from app.permissions import require_permission, enforce_object_policy
```

- [ ] **Step 2: 删除 _check_owner_or_admin 函数**

删除第 27-29 行：
```python
def _check_owner_or_admin(current_user, ecr):
    if current_user.role != "admin" and ecr.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权操作该对象")
```

- [ ] **Step 3: 替换 list_ecrs 门控（第 138 行）**

```
current_user: User = Depends(get_current_active_user)
```
改为：
```
current_user: User = Depends(require_permission("ecr:read"))
```

- [ ] **Step 4: 替换 create_ecr_endpoint 门控（第 182 行）**

```
current_user: User = Depends(get_current_active_user)
```
改为：
```
current_user: User = Depends(require_permission("ecr:create"))
```

- [ ] **Step 5: 替换 get_ecr_detail 门控（第 192 行）**

```
current_user: User = Depends(get_current_active_user)
```
改为：
```
current_user: User = Depends(require_permission("ecr:read"))
```

- [ ] **Step 6: 替换 update_ecr_endpoint 门控（第 203 行）**

```
current_user: User = Depends(get_current_active_user)
```
改为：
```
current_user: User = Depends(require_permission("ecr:update"))
```
并删除第 206 行 `_check_owner_or_admin(current_user, ecr)`，改为：
```python
enforce_object_policy("ecr_owner_or_admin", current_user, ecr)
```

- [ ] **Step 7: 替换 delete_ecr_endpoint 门控（第 215 行）**

```
current_user: User = Depends(get_current_active_user)
```
改为：
```
current_user: User = Depends(require_permission("ecr:delete"))
```
并删除第 219 行 `_check_owner_or_admin(current_user, ecr)`，改为：
```python
enforce_object_policy("ecr_owner_or_admin", current_user, ecr)
```

- [ ] **Step 8: 替换 submit_ecr 门控（第 229 行）**

```
current_user: User = Depends(get_current_active_user)
```
改为：
```
current_user: User = Depends(require_permission("ecr:submit"))
```
并删除第 232 行 `_check_owner_or_admin(current_user, ecr)`，改为：
```python
enforce_object_policy("ecr_owner_or_admin", current_user, ecr)
```

- [ ] **Step 9: 替换 withdraw_ecr 门控（第 249 行）**

```
current_user: User = Depends(get_current_active_user)
```
改为：
```
current_user: User = Depends(require_permission("ecr:withdraw"))
```
删除第 252 行 `_check_owner_or_admin(current_user, ecr)`，改为：
```python
enforce_object_policy("ecr_owner_or_admin", current_user, ecr)
```
删除第 255-256 行重复的内联检查：
```python
if ecr.creator_id != current_user.id and current_user.role != "admin":
    raise HTTPException(status_code=403, detail="仅创建人或管理员可以撤回")
```
（已被 `enforce_object_policy("ecr_owner_or_admin")` 覆盖）

- [ ] **Step 10: 替换 review_ecr 门控（第 271 行）**

```
current_user: User = Depends(get_current_active_user)
```
改为：
```
current_user: User = Depends(require_permission("ecr:approve"))
```
删除第 277-285 行内联审批人检查：
```python
reviewer_ids = set()
for r in (ecr.reviewers or []):
    try:
        reviewer_ids.add(uuid.UUID(r["user_id"]))
    except (ValueError, KeyError):
        pass

if current_user.role != "admin" and current_user.id not in reviewer_ids:
    raise HTTPException(status_code=403, detail="您不是该 ECR 的指定审批人")
```
在 `ecr = get_ecr(db, ecr_id)` 之后、状态检查之前，改为：
```python
reviewer_ids = set()
for r in (ecr.reviewers or []):
    try:
        reviewer_ids.add(uuid.UUID(r["user_id"]))
    except (ValueError, KeyError):
        pass

enforce_object_policy("ecr_approver_or_admin", current_user, ecr, reviewer_ids=reviewer_ids)
```

- [ ] **Step 11: 替换 close_ecr 门控（第 336 行）**

```
current_user: User = Depends(get_current_active_user)
```
改为：
```
current_user: User = Depends(require_permission("ecr:close"))
```

- [ ] **Step 12: 替换 add_affected_item_endpoint 门控（第 354 行）**

```
current_user: User = Depends(get_current_active_user)
```
改为：
```
current_user: User = Depends(require_permission("ecr:update"))
```
在 `item = add_affected_item(db, ecr_id, data)` 之前添加：
```python
ecr = get_ecr(db, ecr_id)
enforce_object_policy("ecr_owner_or_admin", current_user, ecr)
```

- [ ] **Step 13: 替换 remove_affected_item 门控（第 375 行）**

```
current_user: User = Depends(get_current_active_user)
```
改为：
```
current_user: User = Depends(require_permission("ecr:update"))
```
在 `delete_affected_item(db, item_id)` 之前添加：
```python
ecr = get_ecr(db, ecr_id)
enforce_object_policy("ecr_owner_or_admin", current_user, ecr)
```

- [ ] **Step 14: 替换 update_affected_item 门控（第 387 行）**

```
current_user: User = Depends(get_current_active_user)
```
改为：
```
current_user: User = Depends(require_permission("ecr:update"))
```
在 `item = db.query(...)` 之前添加：
```python
ecr = get_ecr(db, ecr_id)
enforce_object_policy("ecr_owner_or_admin", current_user, ecr)
```

- [ ] **Step 15: 替换 get_status_logs 门控（第 409 行）**

```
current_user: User = Depends(get_current_active_user)
```
改为：
```
current_user: User = Depends(require_permission("ecr:read_status_log"))
```

- [ ] **Step 16: 替换 get_bom_trace 门控（第 433 行）**

```
current_user: User = Depends(get_current_active_user)
```
改为：
```
current_user: User = Depends(require_permission("ecr:bom_trace"))
```

- [ ] **Step 17: 替换 cc_ecr 门控（第 453 行）**

```
current_user: User = Depends(get_current_active_user)
```
改为：
```
current_user: User = Depends(require_permission("ecr:cc_manage"))
```

- [ ] **Step 18: 替换 uncc_ecr 门控（第 478 行）**

```
current_user: User = Depends(get_current_active_user)
```
改为：
```
current_user: User = Depends(require_permission("ecr:cc_manage"))
```

- [ ] **Step 19: 验证导入和语法**

```powershell
python -c "from app.routers.ecrs import router; print('ECR router OK')"
```
Expected output: `ECR router OK`

- [ ] **Step 20: Commit**

```bash
git add backend/app/routers/ecrs.py
git commit -m "refactor(ecr): 内联角色检查改为 require_permission + enforce_object_policy"
```

---

### Task 7: ECO Router — 替换全部权限门控

**Files:**
- Modify: `backend/app/routers/ecos.py`

- [ ] **Step 1: 替换导入**

第 13 行：
```
from app.routers.auth import get_current_active_user
```
改为：
```
from app.permissions import require_permission, enforce_object_policy
```

- [ ] **Step 2: 删除 _check_owner_or_admin 函数**

删除第 30-32 行：
```python
def _check_owner_or_admin(current_user, eco):
    if current_user.role != "admin" and eco.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="无权操作该对象")
```

- [ ] **Step 3: 替换 list_ecos 门控（第 146 行）**

```
current_user: User = Depends(get_current_active_user)
```
改为：
```
current_user: User = Depends(require_permission("eco:read"))
```

- [ ] **Step 4: 替换 create_eco_endpoint 门控（第 180 行）**

```
current_user: User = Depends(get_current_active_user)
```
改为：
```
current_user: User = Depends(require_permission("eco:create"))
```

- [ ] **Step 5: 替换 get_eco_detail 门控（第 190 行）**

```
current_user: User = Depends(get_current_active_user)
```
改为：
```
current_user: User = Depends(require_permission("eco:read"))
```

- [ ] **Step 6: 替换 update_eco_endpoint 门控（第 200 行）**

```
current_user: User = Depends(get_current_active_user)
```
改为：
```
current_user: User = Depends(require_permission("eco:update"))
```
删除第 203 行 `_check_owner_or_admin(current_user, eco)`，改为：
```python
enforce_object_policy("eco_owner_or_admin", current_user, eco)
```

- [ ] **Step 7: 替换 delete_eco_endpoint 门控（第 212 行）**

```
current_user: User = Depends(get_current_active_user)
```
改为：
```
current_user: User = Depends(require_permission("eco:delete"))
```
删除第 215 行 `_check_owner_or_admin(current_user, eco)`，改为：
```python
enforce_object_policy("eco_owner_or_admin", current_user, eco)
```

- [ ] **Step 8: 替换 submit_eco 门控（第 226 行）**

```
current_user: User = Depends(get_current_active_user)
```
改为：
```
current_user: User = Depends(require_permission("eco:submit"))
```
删除第 229 行 `_check_owner_or_admin(current_user, eco)`，改为：
```python
enforce_object_policy("eco_owner_or_admin", current_user, eco)
```

- [ ] **Step 9: 替换 withdraw_eco 门控（第 245 行）**

```
current_user: User = Depends(get_current_active_user)
```
改为：
```
current_user: User = Depends(require_permission("eco:withdraw"))
```
删除第 248 行 `_check_owner_or_admin(current_user, eco)`，改为：
```python
enforce_object_policy("eco_owner_or_admin", current_user, eco)
```
删除第 251-252 行重复的内联检查：
```python
if current_user.role != "admin" and eco.creator_id != current_user.id:
    raise HTTPException(status_code=403, detail="仅创建人或管理员可撤回")
```

- [ ] **Step 10: 替换 review_eco 门控（第 263 行）**

```
current_user: User = Depends(get_current_active_user)
```
改为：
```
current_user: User = Depends(require_permission("eco:approve"))
```
删除第 269-273 行内联审批人检查：
```python
uid_str = str(current_user.id)
is_admin = current_user.role == "admin"
is_reviewer = any(r.get("user_id") == uid_str for r in (eco.reviewers or []))
if not is_admin and not is_reviewer:
    raise HTTPException(status_code=403, detail="您不是该 ECO 的指定审批人")
```
在 `eco = get_eco(db, eco_id)` 之后、状态检查之前，改为：
```python
reviewer_ids = set()
for r in (eco.reviewers or []):
    try:
        reviewer_ids.add(uuid.UUID(r["user_id"]))
    except (ValueError, KeyError):
        pass

enforce_object_policy("eco_approver_or_admin", current_user, eco, reviewer_ids=reviewer_ids)
```

- [ ] **Step 11: 替换 start_execution 门控（第 306 行）**

```
current_user: User = Depends(get_current_active_user)
```
改为：
```
current_user: User = Depends(require_permission("eco:execute"))
```

- [ ] **Step 12: 替换 complete_execution 门控（第 319 行）**

```
current_user: User = Depends(get_current_active_user)
```
改为：
```
current_user: User = Depends(require_permission("eco:close"))
```

- [ ] **Step 13: 替换 execute_single_item 门控（第 332 行）**

```
current_user: User = Depends(get_current_active_user)
```
改为：
```
current_user: User = Depends(require_permission("eco:execute_item"))
```

- [ ] **Step 14: 替换 execute_all_items 门控（第 350 行）**

```
current_user: User = Depends(get_current_active_user)
```
改为：
```
current_user: User = Depends(require_permission("eco:execute_all"))
```

- [ ] **Step 15: 替换 list_execution_items 门控（第 365 行）**

```
current_user: User = Depends(get_current_active_user)
```
改为：
```
current_user: User = Depends(require_permission("eco:read"))
```

- [ ] **Step 16: 替换 add_execution_item_endpoint 门控（第 389 行）**

```
current_user: User = Depends(get_current_active_user)
```
改为：
```
current_user: User = Depends(require_permission("eco.affected:manage"))
```

- [ ] **Step 17: 替换 edit_execution_item_endpoint 门控（第 407 行）**

```
current_user: User = Depends(get_current_active_user)
```
改为：
```
current_user: User = Depends(require_permission("eco.affected:manage"))
```

- [ ] **Step 18: 替换 remove_execution_item_endpoint 门控（第 428 行）**

```
current_user: User = Depends(get_current_active_user)
```
改为：
```
current_user: User = Depends(require_permission("eco.affected:manage"))
```

- [ ] **Step 19: 替换 manual_upgrade_item 门控（第 441 行）**

```
current_user: User = Depends(get_current_active_user)
```
改为：
```
current_user: User = Depends(require_permission("eco:revise"))
```

- [ ] **Step 20: 替换 manual_revert_item 门控（第 469 行）**

```
current_user: User = Depends(get_current_active_user)
```
改为：
```
current_user: User = Depends(require_permission("eco:restore"))
```

- [ ] **Step 21: 替换 manual_freeze_item 门控（第 509 行）**

```
current_user: User = Depends(get_current_active_user)
```
改为：
```
current_user: User = Depends(require_permission("eco:freeze"))
```

- [ ] **Step 22: 替换 manual_release_item 门控（第 535 行）**

```
current_user: User = Depends(get_current_active_user)
```
改为：
```
current_user: User = Depends(require_permission("eco:publish"))
```

- [ ] **Step 23: 替换 get_eco_status_logs 门控（第 554 行）**

```
current_user: User = Depends(get_current_active_user)
```
改为：
```
current_user: User = Depends(require_permission("eco:read_status_log"))
```

- [ ] **Step 24: 替换 cc_users_endpoint 门控（第 569 行）**

```
current_user: User = Depends(get_current_active_user)
```
改为：
```
current_user: User = Depends(require_permission("eco:cc_manage"))
```

- [ ] **Step 25: 替换 uncc_user_endpoint 门控（第 580 行）**

```
current_user: User = Depends(get_current_active_user)
```
改为：
```
current_user: User = Depends(require_permission("eco:cc_manage"))
```

- [ ] **Step 26: 替换 bom_trace 门控（第 591 行）**

```
current_user: User = Depends(get_current_active_user)
```
改为：
```
current_user: User = Depends(require_permission("eco:bom_trace"))
```

- [ ] **Step 27: 验证导入和语法**

```powershell
python -c "from app.routers.ecos import router; print('ECO router OK')"
```
Expected output: `ECO router OK`

- [ ] **Step 28: Commit**

```bash
git add backend/app/routers/ecos.py
git commit -m "refactor(eco): 内联角色检查改为 require_permission + enforce_object_policy"
```

---

### Task 8: Sync Router — 添加权限门控

**Files:**
- Modify: `backend/app/routers/sync.py`

- [ ] **Step 1: 添加导入和门控**

将文件内容改为：
```python
"""同步状态查询。"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.permissions import require_permission

router = APIRouter(prefix="/sync", tags=["同步"])


@router.get("/status")
def get_sync_status(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission("sync:read"))
):
    return {
        "parts": 0,
        "assemblies": 0,
        "documents": 0,
        "bom_items": 0,
        "ecrs": 0,
        "ecos": 0,
        "config_items": 0,
    }
```

- [ ] **Step 2: 验证导入**

```powershell
python -c "from app.routers.sync import router; print('Sync OK')"
```
Expected output: `Sync OK`

- [ ] **Step 3: Commit**

```bash
git add backend/app/routers/sync.py
git commit -m "feat(sync): 添加 sync:read 权限门控"
```

---

### Task 9: 清理 — inventory.py 和 projects.py 冗余内联检查

**Files:**
- Modify: `backend/app/routers/inventory.py:222-224`

- [ ] **Step 1: 清理 inventory.py post_document 冗余检查**

删除第 221-224 行的内联 keeper 检查（已被 `enforce_object_policy` 覆盖）：
```python
# 仅指定库管员或管理员可过账
if current_user.role != "admin" and doc.keeper_id != current_user.id:
    raise HTTPException(status_code=403, detail="仅指定库管员可过账")
```
（保留 `enforce_object_policy("inventory_keeper_or_admin", current_user, doc)`）

- [ ] **Step 2: 验证**

```powershell
python -c "from app.routers.inventory import router; print('Inventory OK')"
```

- [ ] **Step 3: Commit**

```bash
git add backend/app/routers/inventory.py
git commit -m "refactor(inventory): 清理 post_document 冗余内联 keeper 检查"
```

> 注：projects.py 的 `_require_member` 中 `user.role != "admin"` 检查保留。这不是冗余的权限检查，而是项目成员管理中的业务规则——admin 可访问所有项目而无需成为正式成员。

---

### Task 10: 最终验证

- [ ] **Step 1: 重新生成权限矩阵（确保一致性）**

```powershell
python tools/gen_permissions.py
```

- [ ] **Step 2: 全局导入验证**

```powershell
python -c "
from app.permissions import require_permission, has_permission, enforce_object_policy
from app.core.permissions import require_permission as rp2
from app.routers.users import router as r1
from app.routers.user_groups import router as r2
from app.routers.documents import router as r3
from app.routers.ecrs import router as r4
from app.routers.ecos import router as r5
from app.routers.configuration import router as r6
from app.routers.inventory import router as r7
from app.routers.projects import router as r8
from app.routers.dashboard import router as r9
from app.routers.custom_fields import router as r10
from app.routers.admin import router as r11
from app.routers.logs import router as r12
from app.routers.sync import router as r13
from app.routers.attachments_v2 import router as r14
print('ALL IMPORTS VERIFIED')
"
```
Expected output: `ALL IMPORTS VERIFIED`

- [ ] **Step 3: 权限矩阵一致性验证**

```powershell
python -c "
from app.permissions._generated import PERMISSIONS, OBJECT_POLICIES
ecr_perms = [k for k in PERMISSIONS if k.startswith('ecr:')]
eco_perms = [k for k in PERMISSIONS if k.startswith('eco:')]
print('ECR permissions:', sorted(ecr_perms))
print('ECO permissions:', sorted(eco_perms))
print('eco:approve present:', 'eco:approve' in PERMISSIONS)
print('eco:approve policy:', OBJECT_POLICIES.get('eco:approve'))

from app.permissions.policies import check_object_policy
policies = ['ecr_owner_or_admin', 'eco_owner_or_admin', 'ecr_approver_or_admin', 'eco_approver_or_admin', 'inventory_keeper_or_admin', 'dashboard_folder_editor', 'project_manager_or_admin', 'document_content_access']
for p in policies:
    try:
        check_object_policy(p, None, None)
    except KeyError as e:
        print(f'Policy missing: {e}')
    except:
        pass
print('All policies registered')
"
```
Expected: 列出所有 ECR/ECO 权限项，`eco:approve present: True`，无 `Policy missing` 错误。

- [ ] **Step 4: 运行现有测试（如有）**

```powershell
pytest backend/tests/ -x --tb=short 2>&1
```
注：如果项目有测试套件，确保无回归。如无测试则跳过此步。

- [ ] **Step 5: Final commit**

```bash
git add backend/app/permissions/_generated.py
git commit -m "chore(permission): 最终验证 — 重新生成权限矩阵"
```
