# 权限门控统一设计与实施

> 将 myPDM 权限管理功能迁移到 plm-unified，统一所有非零部件端点的权限门控。

## 目标

1. **统一双套实现** — 合并 `app/core/permissions.py` 和 `app/permissions/` 为单一模块
2. **消除内联角色判断** — ECR/ECO router 中内联 `_check_owner_or_admin()` 改为 `require_permission()` + `enforce_object_policy()`
3. **补齐缺失门控** — `sync.py` 添加 `sync:read`
4. **统一 import 路径** — 所有 Router 统一从 `app.permissions` 导入
5. **不动零部件模块** — `parts.py`, `iterations.py`, `components.py`, `bom.py` 暂不处理

## 范围排除

- 零部件相关 router（parts, iterations, components, bom）— 业务模型变化较大，后期单独处理
- 前端权限 UI 控制 — 本设计仅覆盖后端 API 门控
- `conversion_compat.py` — DocDoku 兼容回调，无认证设计

---

## 架构设计

### 统一后的权限模块结构

```
backend/app/permissions/
├── __init__.py          # require_permission(), has_permission() [统一入口]
├── _generated.py        # 由 tools/gen_permissions.py 自动生成，只读
└── policies.py          # register_policy(), enforce_object_policy(), 所有策略函数

backend/app/core/permissions.py  → 兼容 re-export
```

### 统一 `require_permission()` 行为

```
用户请求 → get_current_active_user → require_permission("perm:action")
  → PERMISSIONS["perm:action"] 中的 roles 列表包含 user.role？
    ├── 是 → 通过
    └── 否 → user.role == "admin"？（admin 全局豁免）
         ├── 是 → 通过
         └── 否 → 403
```

### import 规范

```python
# 所有 Router 统一：
from app.permissions import require_permission, enforce_object_policy

# 不再使用：
from app.core.permissions import require_permission
```

---

## 文件变更清单

### 模块层

| 文件 | 动作 |
|------|------|
| `app/permissions/__init__.py` | 增加 admin 豁免逻辑，成为统一实现 |
| `app/permissions/policies.py` | 新增 `eco_approver_or_admin` 策略 |
| `app/core/permissions.py` | 改为兼容 re-export |
| `permissions/permissions.json` | 新增 `eco:approve` 权限项 |
| `tools/gen_permissions.py` | 重新生成 `_generated.py` |

### Router 层 — 仅改 import 路径

| 文件 | 变更 |
|------|------|
| `users.py` | `app.core.permissions` → `app.permissions` |
| `user_groups.py` | 同上 |
| `documents.py` | 同上 |
| `configuration.py` | 同上 |
| `custom_fields.py` | 同上 |
| `admin.py` | 同上 |
| `logs.py` | 同上 |
| `dashboard.py` | 同上 |
| `projects.py` | 同上，清理 `_require_member()` 中冗余内联检查 |
| `inventory.py` | 同上，清理 `post_document` 中冗余内联检查 |
| `attachments_v2.py` | `..permissions` → `app.permissions` |

### Router 层 — 重写权限门控

| 文件 | 变更 |
|------|------|
| `ecrs.py` | 所有端点加 `require_permission()`；写操作加 `enforce_object_policy()`；删除 `_check_owner_or_admin()` |
| `ecos.py` | 同上 |
| `sync.py` | 添加 `require_permission("sync:read")` |

---

## ECR/ECO 端点权限映射

### ecrs.py

| 端点 | 新门控 |
|------|--------|
| `GET /ecrs/` | `require_permission("ecr:read")` |
| `POST /ecrs/` | `require_permission("ecr:create")` |
| `GET /ecrs/{id}` | `require_permission("ecr:read")` |
| `PUT /ecrs/{id}` | `require_permission("ecr:update")` + `enforce_object_policy("ecr_owner_or_admin", ...)` |
| `DELETE /ecrs/{id}` | `require_permission("ecr:delete")` + `enforce_object_policy("ecr_owner_or_admin", ...)` |
| `POST /ecrs/{id}/submit` | `require_permission("ecr:submit")` + `enforce_object_policy("ecr_owner_or_admin", ...)` |
| `POST /ecrs/{id}/withdraw` | `require_permission("ecr:withdraw")` + `enforce_object_policy("ecr_owner_or_admin", ...)` |
| `POST /ecrs/{id}/review` | `require_permission("ecr:approve")` + `enforce_object_policy("ecr_approver_or_admin", ..., reviewer_ids=...)` |
| `POST /ecrs/{id}/close` | `require_permission("ecr:close")` |
| `POST /ecrs/{id}/affected-items` | `require_permission("ecr:update")` + `enforce_object_policy("ecr_owner_or_admin", ...)` |
| `PUT /ecrs/{id}/affected-items/{item_id}` | 同上 |
| `DELETE /ecrs/{id}/affected-items/{item_id}` | 同上 |
| `GET /ecrs/{id}/status-logs` | `require_permission("ecr:read_status_log")` |
| `POST /ecrs/{id}/bom-trace/...` | `require_permission("ecr:bom_trace")` |
| `POST /ecrs/{id}/cc` | `require_permission("ecr:cc_manage")` |
| `DELETE /ecrs/{id}/cc/{user_id}` | `require_permission("ecr:cc_manage")` |

### ecos.py

| 端点 | 新门控 |
|------|--------|
| `GET /ecos/` | `require_permission("eco:read")` |
| `POST /ecos/` | `require_permission("eco:create")` |
| `GET /ecos/{id}` | `require_permission("eco:read")` |
| `PUT /ecos/{id}` | `require_permission("eco:update")` + `enforce_object_policy("eco_owner_or_admin", ...)` |
| `DELETE /ecos/{id}` | `require_permission("eco:delete")` + `enforce_object_policy("eco_owner_or_admin", ...)` |
| `POST /ecos/{id}/submit` | `require_permission("eco:submit")` + `enforce_object_policy("eco_owner_or_admin", ...)` |
| `POST /ecos/{id}/withdraw` | `require_permission("eco:withdraw")` + `enforce_object_policy("eco_owner_or_admin", ...)` |
| `POST /ecos/{id}/review` | `require_permission("eco:approve")` + `enforce_object_policy("eco_approver_or_admin", ..., reviewer_ids=...)` |
| `POST /ecos/{id}/execute` | `require_permission("eco:execute")` |
| `POST /ecos/{id}/complete` | `require_permission("eco:close")` |
| `POST /ecos/{id}/execute-item/{item_id}` | `require_permission("eco:execute_item")` |
| `POST /ecos/{id}/execute-all` | `require_permission("eco:execute_all")` |
| `GET /ecos/{id}/execution-items` | `require_permission("eco:read")` |
| `POST /ecos/{id}/execution-items` | `require_permission("eco.affected:manage")` |
| `PUT /ecos/{id}/execution-items/{item_id}` | `require_permission("eco.affected:manage")` |
| `DELETE /ecos/{id}/execution-items/{item_id}` | `require_permission("eco.affected:manage")` |
| `POST /ecos/{id}/execution-items/{item_id}/upgrade` | `require_permission("eco:revise")` |
| `POST /ecos/{id}/execution-items/{item_id}/revert` | `require_permission("eco:restore")` |
| `POST /ecos/{id}/execution-items/{item_id}/freeze` | `require_permission("eco:freeze")` |
| `POST /ecos/{id}/execution-items/{item_id}/release` | `require_permission("eco:publish")` |
| `GET /ecos/{id}/status-logs` | `require_permission("eco:read_status_log")` |
| `POST /ecos/{id}/cc` | `require_permission("eco:cc_manage")` |
| `DELETE /ecos/{id}/cc/{user_id}` | `require_permission("eco:cc_manage")` |
| `POST /ecos/{id}/bom-trace/...` | `require_permission("eco:bom_trace")` |

---

## 新增权限项

### permissions.json

```json
"eco:approve": { "roles": ["admin", "engineer"], "object_policy": "eco_approver_or_admin" }
```

### 新增策略函数

```python
@register_policy("eco_approver_or_admin")
def _eco_approver_or_admin(user, eco, *, reviewer_ids=None, **_):
    return _is_admin(user) or (reviewer_ids is not None and user.id in reviewer_ids)
```

---

## 对象级策略汇总

| 策略名 | 规则 | 应用端点 |
|--------|------|---------|
| `ecr_owner_or_admin` | 仅创建者或 admin | ECR 编辑/删除/提交/撤回/受影响项管理 |
| `ecr_approver_or_admin` | 仅指定的审批人或 admin | ECR 审批 |
| `eco_owner_or_admin` | 仅创建者或 admin | ECO 编辑/删除/提交/撤回 |
| `eco_approver_or_admin` | 仅指定的审批人或 admin | ECO 审批 |
| `inventory_keeper_or_admin` | 仅指定保管人或 admin | 库存单据过账 |
| `dashboard_folder_editor` | 文件夹所有者，或被分享且权限为 edit | 看板文件夹/收藏项操作 |
| `project_manager_or_admin` | 仅项目负责人或 admin | 项目/成员/任务/依赖管理 |
| `document_content_access` | admin 或创建者，或用户组与文档组有交集 | 文档附件内容访问 |

---

## 验证方法

1. 运行 `python tools/gen_permissions.py` 确认生成成功
2. 运行后端测试（如有）确认无回归
3. 手动验证关键端点：
   - guest 用户尝试创建 ECR → 403
   - engineer 用户编辑他人 ECR → 403
   - admin 用户所有操作 → 通过
   - production 用户查看 status-logs → 通过
