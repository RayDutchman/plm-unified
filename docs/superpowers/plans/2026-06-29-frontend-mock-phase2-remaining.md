# 前端 Mock 剩余模块数据（变更 / 库存 / 系统设置）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans（本计划偏前端可视迭代，建议内联执行，配合预览工具 DOM 取证）。Steps 用 `- [ ]` 跟踪。

**Goal:** 为剩余业务模块补 mock 列表/详情数据，让它们以 **myPDM 原界面**渲染出内容（非空）。**完全沿用 myPDM 页面 UI，零页面改动**——只新增 `services/mock/fixtures/*.ts` 并在 `routes.ts` 注册。

**Architecture:** 复用已建的 axios mock 适配层（`api.defaults.adapter = mockAdapter`，`VITE_USE_MOCK=1`）。每模块一个 fixtures 文件，按 `method + url` 路由返回假数据；未命中接口仍 `console.warn + 501`。

**Tech Stack:** 现有 Vite/React/TS 前端 + `services/mock/`。验证用预览工具（dev server 8080）DOM 取证（截图因应用持续轮询难 network-idle，用 `preview_eval` 读 DOM 替代）。

---

## 背景与现状（已验证）

**所有模块页都已用 myPDM 原 UI 正常渲染**（render sweep 实测，无崩溃/overlay）。差别只在有无数据：

| 模块 | 路由 | 状态 | 备注 |
|---|---|---|---|
| 用户看板 / 仪表盘 | /board /dashboard | ✅ 已有数据 | Phase 0/1 |
| 零部件管理 | /parts | ✅ 已有数据 | 统一 PartMaster 页（已建） |
| 构型管理 | /configuration | ✅ 已有数据 | 本轮已补 3 样例 |
| **变更管理** | /ec | ⬜ 空（待补） | 本计划 Task A |
| **库存管理** | /inventory | ⬜ 空（待补） | 本计划 Task B |
| **系统设置** | /settings | 🟡 部分（改密✓/用户✓；自定义字段、操作日志空） | 本计划 Task C |
| 图文档 / 项目 | /documents /projects | ⬜ 空 | 用户 7 模块外，**可选** Task D |

## 通用执行循环（每个 Task 都照此做）

1. `preview_start`（name `frontend`）拿 serverId；导航到目标页（点 nav `a[href=...]`）。
2. `preview_console_logs` 看 `[mock] 未实现的接口: METHOD url` —— 这就是该页真正调用、还没 mock 的端点清单。
3. 读对应 `services/api.ts`（或 `services/*Api.ts`）方法 + 页面/类型，确认返回 shape（数组 or `{items,total}`；字段名）。
4. 新建 `services/mock/fixtures/<module>.ts`，导出 `<module>Routes: MockRoute[]`，按真实 shape 造 2–4 条自洽样例。
5. 在 `services/mock/routes.ts` import 并 spread 进 `routes`。
6. 重载验证：`preview_eval` 读 `main` 文本，确认表格出行、无 501、无 overlay。
7. `npx tsc --noEmit` + `npx vitest run` 全绿后提交：`feat(frontend): <模块> mock 数据`。

> **形状对齐原则**：以**页面组件实际解构**为准（`data.items` vs 数组、字段名），fixture 迁就组件，**绝不改页面**。

---

### Task A: 变更管理（ECR + ECO）

**Files:** Create `frontend/src/services/mock/fixtures/changemgmt.ts`；Modify `routes.ts`

**已知（探查结论）:**
- `ecrApi.list` → `GET /ecrs/`（尾斜杠）；`ecrApi.get` → `GET /ecrs/:id`
- EC 页列：`ECR编号 | 标题 | 状态 | 优先级 | 创建人 | 创建时间 | 操作`
- 状态筛选项：草稿 / 审核中 / 已批准 / 已驳回 / 已关闭（即 status 枚举 `draft/submitted/approved/rejected/closed`）
- ECR 字段（types/index.ts）：`ecr_number, title, status, priority, creator_name, created_at, id`

- [ ] **Step 1: 确认 EC 页是否含 ECO 标签** —— 读 `pages/EC.tsx`，看是否同时调 `ecoApi.list`（`GET /ecos/`）。若是，ECO 一并补。
- [ ] **Step 2: 抓 /ec 页 501 清单**（通用循环 step 2）。
- [ ] **Step 3: 写 fixtures/changemgmt.ts** —— `GET /ecrs/` 返回 `{items:[…], total}`，样例 3 条覆盖不同 status/priority；如需 `GET /ecos/` 同样补。字段名以 `EC.tsx` 解构为准。
- [ ] **Step 4: 注册 + 验证** —— `/ec` 表格出 ECR 行，状态/优先级筛选有内容，无 501/overlay。
- [ ] **Step 5: 提交** `feat(frontend): 变更管理(ECR/ECO) mock 数据`

**验收:** `/ec` 列表非空，呈现 myPDM ECR 界面与数据；点详情若 501，记录留 Task A-后续（详情端点按需补）。

---

### Task B: 库存管理

**Files:** Create `frontend/src/services/mock/fixtures/inventory.ts`；Modify `routes.ts`

**已知:**
- 前端 `services/inventoryApi.ts`（独立模块）；Inventory 页列：`物料 | 仓库 | 批次 | 数量 | 安全库存`；筛选：全部仓库 / 仅看低库存
- 后端实体：Warehouse / InventoryMaterial / InventoryStock / InventoryLedger / InventoryDocument

- [ ] **Step 1: 读 `services/inventoryApi.ts`** —— 列出 Inventory 页首屏调用的端点（仓库列表、库存/物料列表等）与返回 shape。
- [ ] **Step 2: 抓 /inventory 页 501 清单**。
- [ ] **Step 3: 写 fixtures/inventory.ts** —— 仓库 2 个（主仓/线边仓）、物料/库存 3–4 条（含 1 条低于安全库存以验证"仅看低库存"筛选）。字段以页面解构为准。
- [ ] **Step 4: 注册 + 验证** —— `/inventory` 出库存行，"仅看低库存"过滤生效，无 501/overlay。
- [ ] **Step 5: 提交** `feat(frontend): 库存管理 mock 数据`

**验收:** `/inventory` 列表非空，呈现 myPDM 库存界面与数据。

---

### Task C: 系统设置（自定义字段 + 操作日志）

**Files:** Create `frontend/src/services/mock/fixtures/settings.ts`；Modify `routes.ts`（自定义字段需把 `/custom-fields/definitions/` 从 `shell.ts` 的空桩移来并给数据）

**已知:**
- Settings 页 tab：自定义字段 / 数据管理 / 修改密码（✓ 已可用）/ 操作日志
- 自定义字段：`GET /custom-fields/definitions/`（当前 shell.ts 返回 `[]`）→ `customFieldsApi.listDefinitions()`
- 操作日志：`logsApi` → `GET /logs/`；后端实体 OperationLog
- 用户管理已有数据（shell sampleUsers）；**用户组** tab 可能调 `GET /user-groups/`（按需补）

- [ ] **Step 1: 读 `Settings.tsx` + `logsApi` + `customFieldsApi`** —— 确认自定义字段定义与日志的字段 shape。
- [ ] **Step 2: 抓 /settings 各 tab 的 501 清单**（切到自定义字段、操作日志 tab 时触发）。
- [ ] **Step 3: 写 fixtures/settings.ts** ——
  - 自定义字段定义 2–3 条（名称/类型/适用实体）；把 `/custom-fields/definitions/` 路由从 `shell.ts` 移到此并给数据
  - 操作日志 `GET /logs/` 5 条（用户/动作/时间/对象）
  - 如有 `/user-groups/`：2 个用户组
- [ ] **Step 4: 注册 + 验证** —— 自定义字段 tab 出定义行、操作日志 tab 出日志行，无 501/overlay。
- [ ] **Step 5: 提交** `feat(frontend): 系统设置(自定义字段/操作日志) mock 数据`

**验收:** Settings 四个 tab 均有内容（改密、自定义字段、操作日志、数据管理），myPDM 界面完整。

---

### Task D（可选，用户 7 模块外）: 图文档 / 项目

- 图文档 `/documents`（`documentsApi.list` → `GET /documents/`，当前 shell 返回 emptyPage）、项目 `/projects`（`projectApi`）。
- 同样套路补 fixtures。**默认不做**，按 milestones 留到 M7/M8；用户明确要时再开。

---

## 收尾

- [ ] 全部模块补完后：`npx tsc --noEmit` + `npx vitest run` 全绿。
- [ ] 用 finishing-a-development-branch 决定 `feat/frontend-mock` 去向（合并 `dev_myPDM` / PR）。
- [ ] 更新 `milestones.md`：标注"前端各模块 mock 独立运行"已完成（属 M3 提前量，注明后端绑定仍待 M2/M3）。

## Self-Review

- **覆盖**：用户 7 模块中剩余的变更/库存/系统设置 → Task A/B/C；已完成项（看板/仪表盘/零部件/构型/用户/改密）不重复。
- **零自设计**：所有 Task 只动 `services/mock/`，不改任何页面，满足"完全参考 myPDM"。
- **占位**：各 fixture 字段名标注"以页面解构为准"——前端 mock 固有的"先抓 501、再对形状"环节，已在每 Task 的 Step 1–2 固化。
- **次序无强依赖**：A/B/C 相互独立，可任意顺序或并行。
