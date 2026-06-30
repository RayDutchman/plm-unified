# 设计文档：myPDM 全量功能迁移至 plm-unified

> 日期：2026-06-30  
> 状态：已确认  
> 方案：A — 照搬适配（复制 myPDM models/routers/schemas，批量替换 FK → PartMaster）

---

## 1. 背景

plm-unified 已通过 M1（零件 CRUD + 签入签出状态机）和 M2（装配体 + 矩阵合成 + CAD 转换全链路）实现了 DocDoku 侧核心能力。前端 UI 已合并 myPDM 的 13 个页面，但数据层全部走 mock。

本计划将 myPDM 的全部业务模块迁移到 plm-unified 后端，替换前端 mock 数据为真实数据库。

## 2. 核心决策

| 决策 | 选择 |
|------|------|
| 范围 | myPDM 全量 10 个模块（约 35 表、180 端点） |
| 零件模型 | 使用 plm-unified 的 PartMaster/PartRevision/PartIteration（废弃 myPDM components 表） |
| BOM 模型 | 使用 plm-unified 的 part_usage_links + cad_instances（废弃 myPDM bom_items 表） |
| 推进顺序 | 按数据依赖自底向上 |
| 模型策略 | 从 myPDM 照搬 models/routers/schemas，仅改 FK 引用 |

## 3. 架构

```
前端 (React) — 16 页 → 关闭 VITE_USE_MOCK，直连后端
       ↓ REST /api/*
后端 (FastAPI) — 19 个 Router 模块
       ↓ SQLAlchemy
数据库 (PostgreSQL) — ~35 张表
```

### 3.1 模块映射

| 层 | 模块 | 原 myPDM 文件 | plm-unified 目标 | 
|----|------|-------------|------------------|
| 基础 | 用户+用户组 | routers/users.py, user_groups.py | 照搬 |
| 实体 | 零件 | 废弃（components 表） | routers/parts.py ✅ M1 |
| 实体 | 图文档 | routers/documents.py, models.py | 适配 FK |
| 关系 | BOM | 废弃（bom_items 表） | routers/iterations.py ✅ M2 |
| 关系 | 文档实体链接 | document_links JSONB | 适配 FK |
| 流程 | ECR/ECO | routers/ecrs.py, ecos.py, models_ecr.py, models_eco.py | 适配 FK |
| 构型 | 构型项+方案 | routers/configuration.py, models_configuration.py | 适配 FK |
| 库存 | 仓库+物料+库存+单据 | routers/inventory.py, models_inventory.py | 适配 FK |
| 项目 | 项目+任务+甘特图 | routers/projects.py, models_project.py | 照搬 |
| 支撑 | 仪表盘/看板 | routers/dashboard.py | 适配 FK |
| 支撑 | 自定义字段 | routers/custom_fields.py | 照搬 |
| 支撑 | 操作日志 | routers/logs.py | 照搬 |
| 支撑 | 附件 | routers/attachments_v2.py | 适配文档 FK |
| 支撑 | 权限 | permissions/permissions.json | 直接复制 |

## 4. FK 映射清单

| 原 myPDM 引用 | plm-unified 替代 | 影响模块 |
|--------------|-----------------|---------|
| `component_id` (FK→components) | `part_master_id` (FK→part_masters) | 文档链接、ECR受影响条目、ECO执行项、库存来源、构型项零件、仪表盘收藏 |
| `child_id`/`parent_id` (BOM) | 废弃（part_usage_links 替代） | BOM 模块 |
| `version` (字符串 A~ZZ) | part_revisions.version | ECR、ECO |
| `user_id` / `group_id` | 不变 | 全部 |
| `document_id` | 不变 | 文档相关 |

## 5. users 表补充

当前 plm-unified users 表缺：
- `department` VARCHAR(128)
- `phone` VARCHAR(32)

新增 Alembic 迁移 `0004_extend_users`。

## 6. 路由挂载

```python
# main.py 新增
app.include_router(documents.router, prefix="/api")
app.include_router(bom.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(user_groups.router, prefix="/api")
app.include_router(ecrs.router, prefix="/api")
app.include_router(ecos.router, prefix="/api")
app.include_router(configuration.router, prefix="/api")
app.include_router(inventory.router, prefix="/api")
app.include_router(projects.router, prefix="/api")
app.include_router(dashboard.router, prefix="/api")
app.include_router(custom_fields.router, prefix="/api")
app.include_router(logs.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
app.include_router(attachments_v2.router, prefix="/api")
app.include_router(sync.router, prefix="/api")
```

## 7. 前端适配

1. 关闭 `VITE_USE_MOCK`，axios 直连后端
2. 字段名从 snake_case 适配为 camelCase（plm-unified schema 层已自动输出 camelCase）
3. `bon_items` 相关请求改为 `/api/bom/` 路径
4. PartMaster 页面（`/parts`）字段已匹配 `GET /api/parts/{number}`

## 8. 实施阶段

| Phase | 内容 | 工期 |
|-------|------|------|
| 0 基础设施 | 补 user 字段 + 权限复制 + 路由框架 | 1-2 天 |
| 1 实体层 | 用户 CRUD + 图文档 CRUD + 附件上传 | 3-4 天 |
| 2 关系层 | BOM 树/对比/反查（适配 part_usage_links ）+ 文档链接 | 3-4 天 |
| 3 流程层 | ECR + ECO（~31 端点，适配 PartMaster/M2 状态机） | 5-7 天 |
| 4 构型+库存+项目 | 构型项/方案 + 仓库/物料/库存/单据 + 项目/任务/甘特图 | 7-10 天 |
| 5 支撑+集成 | 仪表盘 + 自定义字段 + 日志 + 全页面回归 | 3-4 天 |

**总工期：22-31 个工作日**

## 9. 风险

| 风险 | 缓解 |
|------|------|
| ECR/ECO 执行项依赖 PartMaster 状态机，部分 myPDM 操作（force_undo_checkout、强制改状态）无对应 API | 逐步补充分 admin 旁路端点 |
| 库存模块 ref_entity_id 原指向 component_id，改为 PartMaster UUID 后溯源逻辑需验证 | 迁移后全链路集成测试 |
| conversion 容器的 jar 包和 LFS 工具是 M2 专属，M3 无依赖 | 维持容器不变 |
| 前端关闭 mock 后一次性暴露所有不兼容问题 | 逐页灰度切换，保留 mock 回退开关 |
