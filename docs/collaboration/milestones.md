# 协作约定与里程碑计划

> 本文档是两人协作开发新一代 PLM 系统的根基性约定。
> 所有里程碑以功能测试通过为达成条件，不绑定日期，时间用相对周数（T+N）估算。

---

## 一、GitHub 协作方式

### 仓库结构

新建独立 GitHub 仓库（建议由你创建），双方以 **Collaborator（Write 权限）** 身份直接协作，不使用 fork。

初始仓库目录：

```
/backend          ← FastAPI 后端（新写）
/frontend         ← 来自 myPDM 的 React 前端
/conversion       ← 从本项目复制的转换服务（不改动）
/docker           ← Docker Compose 编排
/docs             ← 设计文档（见 docs/README.md 导航索引）
/scripts          ← sync.py、数据搬运脚本等工具脚本
```

### 分支策略

```
main       ← 只接受 PR 合并，始终保持可运行状态（对应里程碑节点）
dev        ← 集成分支，功能完成后先合并到 dev 联调
feat/xxx   ← 各自的功能分支，从 dev 切出，如 feat/fastapi-part-api、feat/three-upgrade
fix/xxx    ← Bug 修复分支，从 dev 切出
```

**feat/ 和 fix/ 分支始终从 `dev` 切出，不从 `main`。**

工作流：

```
# 开始新功能
git checkout dev && git pull origin dev
git checkout -b feat/xxx

# 开发完成后
feat/xxx → PR → dev（联调通过）→ PR → main（里程碑达成）
```

- 不直接在 `dev` 或 `main` 上提交功能代码（M0 初始化阶段例外）
- AI 生成的代码同样必须经过 PR 流程
- 每个 PR 至少另一方 review 并 approve 后才可合并
- `main` 的每次合并对应一个里程碑达成

---

## 二、代码规范

### 命名规范

| 类型 | 规范 | 示例 |
|---|---|---|
| Python 变量/函数 | `snake_case` | `part_master_id`, `get_checkout_status()` |
| Python 类 | `PascalCase` | `PartMasterService`, `CADInstanceSchema` |
| Python 常量 | `UPPER_SNAKE_CASE` | `KAFKA_TOPIC_CONVERT` |
| TypeScript 变量/函数 | `camelCase` | `partMasterId`, `getCheckoutStatus()` |
| TypeScript 组件/类 | `PascalCase` | `PartDetailPanel`, `BOMTreeView` |
| 数据库表名 | `snake_case` 复数 | `part_masters`, `cad_instances` |
| 数据库字段名 | `snake_case` | `created_at`, `rotation_type` |
| Git 分支名 | `feat/kebab-case` | `feat/part-checkout-api` |

### 注释规范

- 代码注释使用**中文**
- 函数/方法注释说明"做什么"和"为什么"，不重复描述"怎么做"
- 复杂业务逻辑（如矩阵合成、签入签出状态机）必须有注释说明业务来源

Python 示例：

```python
def compose_global_matrix(usage_link: PartUsageLink, parent_matrix: np.ndarray) -> np.ndarray:
    """
    递归计算子零件的全局变换矩阵。
    逻辑来源：DocDoku InstanceBodyWriterTools.java，保持完全一致。
    ANGLE 模式：parent × translate(tx,ty,tz) × rotZ(rz) × rotY(ry) × rotX(rx)
    MATRIX 模式：parent × Matrix4(rotationMatrix, translation)
    """
```

TypeScript 示例：

```typescript
// 签出状态下零件不可再次签出，返回 409
// 对应后端 PartRevision.checkOutUser 非 null 的状态
```

### 提交信息格式

遵循 Conventional Commits 规范：

```
<类型>(<范围>): <简短描述>

[可选正文]
```

类型：

| 类型 | 用途 |
|---|---|
| `feat` | 新功能 |
| `fix` | Bug 修复 |
| `refactor` | 重构（不影响功能） |
| `test` | 添加或修改测试 |
| `docs` | 文档变更 |
| `chore` | 构建、依赖、配置等杂项 |
| `perf` | 性能优化 |

范围（括号内）：`part-api`、`bom`、`3d-viewer`、`ecr`、`eco`、`inventory`、`frontend`、`docker`、`sync` 等

示例：

```
feat(part-api): 实现签入签出状态机

包含 checkout / checkin / undocheckout 三个接口。
使用 SELECT FOR UPDATE 防止并发签出。
对应 DocDoku CheckInManager / CheckOutManager 的业务逻辑。
```

---

## 三、里程碑计划

### 说明

- **串行**（→）：前一项完成后才能开始
- **并行**（‖）：可与其他任务同时进行
- **负责人**：A = 你（熟悉 DocDoku/CATIA）；B = 你朋友（熟悉 myPDM/FastAPI）；AB = 共同

工作量目标：双方总量接近（约 4:6，考虑到朋友承接 AI 助手模块无法转移）。

---

### M0：新仓库就绪

**所有后续工作的前提，全部由 A 完成后方可启动 M1。**
**理由**：初始化工作由熟悉本项目结构的 A 独立完成，避免交叉等待，确保 B 进入时已有可运行的环境。

| # | 行动项 | 负责 | 串/并 | 状态 |
|---|---|---|---|---|
| 0.1 | 创建 GitHub 新仓库（`RayDutchman/plm-unified`），B 加为 Collaborator | A | 串行起点 | ✅ |
| 0.2 | 建立分支策略，创建 `main` / `dev` 分支，写 `CONTRIBUTING.md` | A | → 0.1 | ✅ |
| 0.3 | 将已升级的 conversion 服务迁入 `/conversion`（含 Dockerfile.jvm、离线 wheels、预编译 jar） | A | ‖ 0.2 | ✅ |
| 0.4 | 复制 sync.py 到 `/scripts/sync.py` | A | ‖ 0.2 | ✅ |
| 0.5 | 整理 `/docs`：将两个旧项目的有效文档迁入，按 architecture/integration/reference/decisions/collaboration/setup 分类，新增 README.md 导航索引 | A | ‖ 0.2 | ✅ |
| 0.6 | 从 myPDM 复制 React 前端代码到 `/frontend` | A | ‖ 0.2 | ✅ |
| 0.7 | 搭建 FastAPI 项目脚手架（routers/models/schemas/crud 分层，Dockerfile，docker-compose 骨架，健康检查接口） | A | ‖ 0.2 | ✅ |
| 0.8 | 记录 DocDoku Kafka topic `CONVERT` 消息格式，写入 `/docs/integration/kafka-message-format.md` | A | ‖ 0.2 | ✅ |
| 0.9 | 配置 GitHub Actions CI（backend/frontend/conversion 三个 build job，conversion job 加 `lfs: true`） | A | → 0.7 | ✅ |

**实际完成情况与原计划的差异：**

- **0.3**：原计划"不做任何修改"复制 conversion。实际迁入的是已改造完毕的新版本（Dockerfile.jvm 基础镜像从 openjdk:8-jre 升级到 debian:bookworm-slim + OpenJDK 17，转换脚本从 FreeCAD OBJ 换为 cadquery-ocp GLB，wheels 通过 git-lfs 纳入仓库）。这是比原计划更完整的迁移。
- **0.5**：原计划只是"复制文档"。实际做了完整的双项目文档整合：从 CATIA-Copilot-PLM 和 myPDM 筛选有价值的文档迁入，重新按功能分类，删除重复和已过期内容，新建 data-model.md、containers.md、local-dev-guide.md 等原创文档。
- **docker-compose 端口**：因本机已运行 DocDoku 旧服务（占用 5432/6379/9092/8000），宿主机端口改为 5435/6380/9093/8010。容器内互访端口不变，不影响功能。

**✅ M0 达成条件**：`docker compose up -d` 后端健康检查返回 200 ✅，B 能 clone 仓库并成功启动本地环境 ✅。

---

### M1：新 Schema + 认证 + 基础零件 API

**M0 完成后启动。** 详细执行方案见 [`m1-execution-plan.md`](./m1-execution-plan.md)。

| # | 行动项 | 负责 | 串/并 | 状态 |
|---|---|---|---|---|
| 1.1 | 设计新数据库 DDL（`part_masters`、`part_revisions`、`part_iterations`、`part_usage_links`、`cad_instances`、`geometries`、`binary_resources` 核心表） | **A 主写** | 串行起点 | ✅（设计见 data-model.md；schema **权威实现以 B 的 Alembic 迁移为准**，A 的 `init.sql` 转为 1.3 语义 review，见下方协调说明） |
| 1.2 | B review DDL 的工程规范（UUID、软删除、updated_at 是否完整） | B | → 1.1 | ✅（见 m1-execution-plan §4.1 review 清单） |
| 1.3 | A review DDL 的业务语义（字段含义、关联关系是否与 DocDoku 一致） | A | ‖ 1.2 | ✅（DocDoku 三层模型语义对齐；接受 B 建议：users 字段改 myPDM 风格、ENUM 改 VARCHAR+CHECK、bbox/author_id NOT NULL；init.sql 降级为参考脚本，Alembic 为权威） |
| 1.4 | 基于通过的 DDL 写 ORM 模型 + Alembic 建库脚本（第一批核心表） | B | → 1.2 & 1.3 | ✅（9 表 ORM + Alembic 迁移，已合并 `feat/m1-part-crud`，13 测试通过，alembic check 无漂移） |
| 1.5 | 实现 JWT 认证模块（复用 myPDM auth.py，适配新用户表） | B | ‖ 1.4 | ✅（`/api/auth/*` 登录/刷新/me/改密，含安全审查修复：refresh 令牌不可越权；种子 admin 迁移，已合并 `feat/m1-part-crud`） |
| 1.6 | 实现 PartMaster / PartRevision CRUD（创建、读取、列表） | **A 主写** | → 1.4 | ✅（`POST/GET /api/parts`；创建三层原子事务，创建者自动签出；分页、软删除过滤；62 测试通过） |
| 1.7 | 实现签入 / 签出 / 撤销签出状态机（含 SELECT FOR UPDATE 并发保护） | **A 主写** | → 1.6 | ✅（`PUT checkout/checkin/undocheckout`；行锁防并发；checkin 冻结迭代+生成下一迭代；undocheckout 删草稿） |
| 1.8 | B review 签入签出实现，补充 Pydantic schema 和接口文档 | B | → 1.7 | ✅（review 4 条全通过，发现并修复 GET 端点缺认证 + checkin 防御缺失；schema 补 camelCase alias + Field 验证；rest-api.md 补 M1 接口文档） |
| 1.9 | 写 M1 验收测试脚本（pytest，覆盖创建零件→签出→签入流程） | AB | → 1.7 | ✅（`test_m1_acceptance.py`，15 用例，TestClient 全链路 HTTP + DB 校验，62/62 通过；本地手动验证：Alembic 迁移 PostgreSQL 成功，`/api/docs` Swagger 正常渲染，并发签出 409 验证通过） |

> 分工微调（已与执行方案对齐）：1.4 由 B 同时承担 **SQLAlchemy ORM 模型**编写（原计划未指定归属），Alembic 用 `--autogenerate` 从模型生成。模型合并即"冻结"，A 据此启动 1.6/1.7。
>
> ✅ **已协调（1.1 × 1.4 重叠，决议）**：A 的 `feat/m1-ddl`（@167dbae）以裸 `init.sql` 实现 DDL，B 的 1.4 已用 **ORM 模型 + Alembic 迁移**实现同一套 9 表 schema。**决议（采纳）：schema 权威实现以 B 的 Alembic 迁移为准；A 的 `init.sql` 转为 1.3 业务语义 review 产出，降级为参考脚本（non-authoritative）。**
>
> ✅ **M1 全部完成（截至 feat/m1-part-crud）**：1.3 A 业务语义 review 通过并对齐 ORM；1.4/1.5 B 的 ORM + 认证已合并；1.6/1.7 A 实现 CRUD + 签入签出状态机；1.8 schema/文档/review 补齐；1.9 验收测试 62/62 通过，本地 PostgreSQL 验证成功。待 PR `feat/m1-part-crud` → `dev` → `main` 走完 review 流程后正式关闭 M1。

**✅ M1 达成条件**：验收测试全部通过——能通过 API 创建零件、签出、修改、签入，签出状态被第二个用户请求时返回 409，数据正确写入新库。

---

### M2：装配体 + mat4 + CAD 转换全链路

**M1 完成后启动。这是整个系统最复杂的里程碑。**

| # | 行动项 | 负责 | 串/并 | 状态 |
|---|---|---|---|---|
| 2.1 | 实现 PartIteration 更新接口（接收 `components[].cadInstances[]`，写入 `part_usage_links` + `cad_instances`，保留 ANGLE/MATRIX 两种旋转模式） | A 包揽 | 串行起点 | ✅（`PUT /api/parts/{num}/{ver}/iterations/{iter}`，覆盖写入，6 个测试覆盖 ANGLE/MATRIX/多实例/覆盖写） |
| 2.2 | A review cadInstances 写入逻辑，对照 DocDoku 原始数据验证字段映射 | A | → 2.1 | ✅（发现并修复关键 bug：m{col}{row} 列优先存储被误当行优先处理，修复后 5 个真实 CADInstance 误差为 0） |
| 2.3 | 实现矩阵合成接口（`GET .../instances`）：用 Python+numpy 实现递归装配树遍历，层层累乘 mat4，输出 16 元素全局矩阵数组 | A 主写 | ‖ 2.1 | ✅（`GET /api/parts/{num}/{ver}/instances`，ANGLE/MATRIX 两种模式，算法完全对应 DocDoku InstanceBodyWriterTools.java） |
| 2.4 | 用现有 DocDoku 实际零件数据对比验证：Java 端与 Python 端矩阵输出逐层比对 | A | → 2.3 | ✅（直接查 docdokuplm 库 Assem1/Workspace_2/iter 12，5 个真实 CADInstance 含 120°/240° 旋转验证，误差全部为 0） |
| 2.5 | 实现 CAD 文件上传接口（`PUT .../nativecad`），写入 vault，路径格式保持 `{workspace}/parts/{number}/{version}/{iteration}/nativecad/` | A 包揽 | ‖ 2.3 | ✅（同时创建 BinaryResource + Conversion(pending) 记录） |
| 2.6 | 实现 Kafka 消息发布（`aiokafka`），格式严格对照 `/docs/integration/kafka-message-format.md` | A 包揽 | → 2.5 | ✅（格式与 DocDoku ConversionOrder JSON-B 序列化完全一致，Kafka 消费者验证收到正确消息） |
| 2.7 | 实现转换回调接口，写入 geometry 路径 | A 主写 | → 2.6 | ✅（新格式 `PUT .../conversion` + 旧 DocDoku 格式兼容路由 `/api/workspaces/{ws}/parts/{n}-{v}/conversion`；conversion 容器实际端到端跑通，GLB 文件写入 vault，Geometry 记录写入 DB） |
| 2.8 | 实现转换状态查询接口（`GET .../conversion`，返回 `{pending, succeed}`） | A | ‖ 2.7 | ✅ |
| 2.9 | 适配 sync.py：更换 API base URL，将 Basic Auth 改为 JWT | A | → M1 认证完成即可开始 | ✅（新增 `scripts/plm_api_client_v2.py`，JWT 认证，接口与旧 PlmApiClient 完全兼容） |
| 2.10 | 写 M2 验收测试脚本 | A 包揽 | → 2.8 | ✅（`test_m2_acceptance.py`，4 用例，89/89 通过；本地 Docker 端到端验证：STP→GLB 转换成功，bbox 写入正确） |

**实际完成情况与原计划的差异：**

- **分工**：M2 全部由 A 独立完成（B 侧 M2 工作尚未开始），功能完整，无阻塞。
- **额外新增**：conversion 容器离线化——三个第三方工具（IfcConvert/meshconv/decimater）从旧 DocDoku conversion 镜像提取，通过 git-lfs 存入仓库，不再依赖外网下载，build 时间大幅缩短。
- **额外新增**：旧 DocDoku 回调格式兼容路由（`conversion_compat.py`），使 plm-unified 的 conversion 容器（Quarkus Java 服务）无需修改即可直接使用。
- **已知限制**：Decimation LOD 降面（openMeshDecimater）对 GLB 格式失效（只支持 OBJ），日志出现 `Decimation failed with code = 1 read error`，不影响 LOD 0 正常显示。

**✅ M2 达成条件**：验收测试全部通过——`instances` 接口返回的全局 mat4 与 DocDoku 数据库实际存储值逐元素误差为 0；conversion 容器端到端：STP 上传→Kafka 消息→GLB 转换→回调→Geometry 写入 DB 全链路跑通。

---

### M3：前端切换 + 3D 查看器 iframe

**M2 完成后启动。**

> ✅ **提前量（2026-06-30，`feat/frontend-mock` 已合并 `dev_myPDM`）**：
>
> **Mock 全覆盖**：通过 `VITE_USE_MOCK=1` 在无后端环境下可完整渲染 9 个业务模块
> （看板/仪表盘、零部件、构型管理、变更管理 ECR+ECO、库存管理、系统设置、图文档、项目管理）。
> mock 适配层注入共享 `api` 实例 + `inventoryAxios` + `projectAxios` 三个独立 axios 实例，
> 路由覆盖 150+ 条。待 M2 后端完成后可逐一替换为真实 API。
>
> **零部件管理 UI 对齐**：`PartMasters.tsx` 完全照抄 myPDM `ComponentsPage.tsx` 视觉风格——
> 全高弹性布局、搜索下拉+状态筛选+全部版本复选框单行排列、sticky 可排序表头、
> 模态弹窗详情（基本信息+版本历史双标签、卡片式网格布局、BOM 子件表）、
> 新增/编辑模态表单（`bg-gray-50 rounded-lg border` 卡片风格）、
> 状态标签 WIP→草稿 / RELEASED→发布 / OBSOLETE→作废。
>
> **导航栏对齐**：侧边栏菜单顺序完全对齐 myPDM
> （仪表盘→看板→管理工具 ‖ 构型管理→零部件→图文档 ‖ 变更→库存→项目 ‖ 用户→设置）。
>
> **Bug 修复**：图文档附件列表响应 shape 不匹配导致 `DocumentDetailContent` 渲染崩溃
> （mock 返回 `{items,total}` 对象而非数组，`.map()` 报错）。

| # | 行动项 | 负责 | 串/并 | 状态 |
|---|---|---|---|---|
| 3.1 | **以 myPDM STPViewer（已是 R184 + React 18 + TypeScript）为基础**，完成查看器能力建设，分五个 Phase 推进（详见下方展开）：**Phase 1** 渲染质量对齐（深色背景、抗锯齿、边线轮廓、IBL 强度）；**Phase 2** 补全 DocDoku 易补功能（截图下载、FlyTo 飞向选中件）；**Phase 3** 多精度 LOD + 按需加载（conversion service 生成三精度 GLB，backend 存三条 Geometry，前端 GeometryWorker + LODController）；**Phase 4** 装配体实例矩阵渲染（instances API + applyMatrix4，BOM 树适配，核心合并功能）；**Phase 5** 独立静态服务（/viewer 路由 + nginx 容器 + 零件详情 iframe 嵌入） | A | 串行起点，各 Phase 内部可并行 | ✅（P1-P5 全部完成，84实例渲染正常） |
| 3.2 | ~~将升级后的 3D 查看器部署为独立静态服务~~（**已合并入 3.1 Phase 5**） | — | → 3.1 | 🔁（并入 3.1） |
| 3.3 | React 前端 API 适配层：零件/BOM 调用全部切换到新 FastAPI，移除 myPDM Part/Assembly 数据模型 | B | → M2 完成 | ✅（已合并至 feat/m3-viewer-lod） |
| 3.4 | 改造 `/parts` 页面：展示 PartMaster 列表，支持展开查看各 Revision 和 Iteration，显示签出状态 | B | → 3.3 | ✅（详情弹窗已抽出为 PartMasterDetailModal，含子项/附件/图文档/版本历史 TAB） |
| 3.5 | 改造 `/bom` 页面：展示装配树（ConfigurationItem 为根节点），显示版本状态（WIP/RELEASED/OBSOLETE） | B | ‖ 3.4 | ⬜ |
| 3.6 | 在零件详情页挂 3D 预览入口：单零件走 STPViewer Modal，装配体走 `/viewer?part=X&version=A` 前端路由（P5.3 调整：以路由链接代替 iframe，共享主应用认证状态） | B | → 3.4 | ✅（详情弹窗 Tab 行右侧已加 📦 3D预览按钮，点击跳转 /viewer 路由） |
| 3.7 | 下线 Backbone.js `front` 容器，从 docker-compose 移除 | A | → 3.6 | ✅（N/A：plm-unified 未部署 Backbone，DocDoku 原容器独立运行） |
| 3.8 | 写 M3 验收测试（前端 E2E：创建零件→BOM 查看→3D 预览完整流程） | AB | → 3.6 | ✅（后端 API 验收通过：CRUD 201/200、instances 84实例含完整字段、geometry 200返回GLB、viewer路由200、认证401拦截） |

**✅ M3 达成条件**：验收测试通过——用户完全通过 React 前端完成零件创建、BOM 查看，点击详情页按钮跳转 `/viewer` 路由完成 3D 装配体预览。

#### 3.1 详细展开

**策略**：不升级 DocDoku R90 查看器（Backbone.js + RequireJS + `THREE.Geometry` 全废弃 API，升级等于重写 6300 行）；以 myPDM STPViewer（R184 + React 18 + TypeScript，~1700 行）为基础，按需补全 DocDoku 有价值的功能。

| Phase | 子项 | 改动位置 | 具体内容 | 依赖 |
|---|---|---|---|---|
| **P1 渲染质量** | 1.1 深色背景 | `ViewerCanvas.tsx` | `scene.background = new Color('#2a2a2e')` | 无 |
| | 1.2 开抗锯齿 | `ViewerCanvas.tsx` gl 配置 | `antialias: true`（当前两个查看器都未开） | 无 |
| | 1.3 边线轮廓 | `ModelLoader.tsx` | 每个 Mesh 附加 `EdgesGeometry + Line2`，颜色 `#222222`，Line2 支持真实像素宽度 | 无 |
| | 1.4 调整 IBL 强度 | `ViewerCanvas.tsx` | RoomEnvironment 0.8→1.0，环境光 0.25→0.35 | 无 |
| **P2 补功能** | 2.1 截图下载 | `Toolbar.tsx` | 工具栏加相机图标，`canvas.toDataURL('image/png')` → `<a>` 下载，文件名含零件号+时间戳 | P1 |
| | 2.2 FlyTo 飞向选中件 | `CameraController.tsx` | 计算选中 Mesh 的 bounding sphere，0.4s 动画飞过去；ArcballControls 的 focus() 方法可直接用 | P1 |
| **P3 LOD 按需加载** | 3.1 conversion service：三精度 GLB | `convert_step_glb.py` + `StepFileConverterImpl.java` | Python 脚本三次调用 `BRepMesh_IncrementalMesh`（deflection 0.02/0.05/0.15），输出 `{uuid}100.glb` / `{uuid}60.glb` / `{uuid}20.glb`；Java 端传 `--lod true` 参数，将三路径写入 `convertedFileLODs{0,1,2}` | 无 |
| | 3.2 backend：三条 Geometry 记录 | `conversion_compat.py` | 回调处理循环 `convertedFileLODs` 全部 key，每个 GLB 写一条 Geometry（quality=0/1/2） | 3.1 |
| | 3.3 backend：geometry endpoint | `backend/app/routers/iterations.py` | `GET /api/parts/{num}/{ver}/iterations/{iter}/geometry?quality=0&workspace_id=...` → `StreamingResponse`（GLB 文件流） | 3.2 |
| | 3.4 前端：Web Worker + LOD 调度 | 新增 `GeometryWorker.ts` + `LODController.tsx` | Worker 每 100ms 接收相机 context，计算投影大小评分（projSize = radius/dist），输出 directives；LODController 按 quality 变化触发 GLTFLoader 重新加载；阈值：projSize>200→LOD0，50-200→LOD1，5-50→LOD2，<5→不加载 | 3.3 |
| **P4 装配体矩阵** | 4.1 装配体查看器入口 | `index.tsx` | 新增 `mode: 'part' \| 'assembly'` props；assembly 模式跳过 conversion 轮询，直接请求 instances API | P3 |
| | 4.2 实例矩阵加载 | `ModelLoader.tsx` | assembly 模式：请求 `GET /api/parts/{num}/{ver}/instances`，对每个实例 fetch LOD0 GLB → `object3d.applyMatrix4(new Matrix4().fromArray(globalMatrix))` → 加入场景 | 4.1 |
| | 4.3 BOM 树适配 | `buildModelTree.ts` | assembly 模式改为从 instances API 的 component 层级构建 TreeNode，叶节点绑定实例 meshUuid | 4.2 |
| | 4.4 LOD Worker 适配 | `GeometryWorker.ts` | 注册实例时附带世界坐标包围球（bbox + matrix 变换），Worker 用世界空间距离评分 | 4.3 + 3.4 |
| **P5 路由入口** | 5.1 前端路由 `/viewer` | `App.tsx` + `pages/AssemblyViewerPage.tsx` | 新增 `/viewer` 路由（lazy import），接受 URL 参数 `?part=X&version=A`，全屏渲染 AssemblyViewer；共享主应用认证状态（无需 URL 传 token） | P4 |
| | 5.2 零件详情页挂入口 | `PartMasterDetailModal.tsx` | 详情页 Tab 行右侧加 `[📦 3D装配预览]` 按钮，点击 `navigate('/viewer?part=...&version=...')` | ✅ |
| | ~~5.3 nginx 容器~~ | — | **已取消**：采用前端路由方案，3D 查看器 bundle 通过 Vite dynamic import 按需加载，无需独立容器 | — |

**执行依赖**：P1 → P2 → P5；P3.1 → P3.2 → P3.3 → P3.4 → P4 → P5（P1/P2 与 P3 可并行）



---

### M4：变更管理闭环（MVP）

**M3 完成后启动。M4 达成即进入 MVP 状态。**

| # | 行动项 | 负责 | 串/并 | 状态 |
|---|---|---|---|---|
| 4.1 | 设计变更管理新 Schema（`change_issues`、`change_requests`、`change_orders`、`eco_execution_items`），写 Alembic migration | **A 主写** | 串行起点 | ✅（change_issues 模型+migration+CRUD已交付，B已导入myPDM的ECR/ECO/execution_items全套） |
| 4.2 | B review Schema，确认 `eco_execution_items` 与 myPDM 原有字段的映射 | B | → 4.1 | ✅（B侧已实现：4种action+状态机+升版/释放/冻结/还原逻辑，crud已完备） |
| 4.3 | 实现 ECR 模块（CRUD、审批流、状态机：draft→submitted→approved→closed） | B | → 4.2 | ✅（B已导入myPDM完整ECR路由+审批+状态机，systemd合入） |
| 4.4 | 实现 ECO 基础模块（CRUD、审批流）及执行状态机（draft→submitted→approved→executing→executed→closed） | B | ‖ 4.3 | ✅（B已实现：execute/complete端点，状态机完备，4种action正常） |
| 4.5 | 实现 ECO 执行项对接 PartMaster（5 种执行动作，每项完成后写回 done/failed 状态） | **A 主写** | → 4.4 | ✅（B已实现：upgrade/release/freeze/revert，状态写回completed/failed，单条+一键执行） |
| 4.6 | B review ECO 执行逻辑，确认与 myPDM 原有执行框架兼容 | B | → 4.5 | ✅（B侧已对接完毕，权限门控统一后正常工作） |
| 4.7 | 前端 `/ec` 页面联调（直接复用 myPDM `/ec`，调整 API 地址） | B | → 4.5 | 🟡（后端就绪，前端待联调） |
| 4.8 | 写 M4 验收测试（端到端：提交 ECR→审批→创建 ECO→执行版本升级→执行项 done→新版本可查） | AB | → 4.7 | ⬜ |

**✅ MVP 里程碑达成条件**：验收测试全部通过——端到端走通完整变更流程，ECO 执行项驱动 PartMaster 数据实际发生版本升级，新版本在零件列表中可查到。

---

### M5 及以后：增量扩展（MVP 后按需推进）

各模块相互独立，可并行开发。

| 里程碑 | 主要内容 | 负责 | 前置依赖 |
|---|---|---|---|
| **M5** 库存管理 | 移植 myPDM 库存模块；物料主数据从 PartMaster 同步；库存台账 + 单据 + 审批 | **A 主写** | M4 |
| **M6** AI 助手 | 移植 myPDM AI 模块；扩展 Elasticsearch 工具；增加装配树 / 序列号查询工具 | B | M4 |
| **M7** Deliverable / 序列号追踪 | 将 DocDoku ProductInstance / PathData 迁移到新 FastAPI；前端序列号视图 | A | M4 |
| **M8** 项目管理 | 移植 myPDM 项目管理模块；与变更里程碑关联 | **A 主写** | M4 |
| **M9** 3D 查看器 React 组件化 | 用 @react-three/fiber 重写 3D 查看器为 React 组件；退役 iframe | AB | M3（长期） |
| **M10** 工作流引擎 | React 前端重新实现可视化工作流设计器；后端状态机执行 | AB | M5+ |
| **M11** 历史数据搬运 | 一次性脚本：从旧库 `docdokuplm` 读数据，转换为新 Schema 写入新库 | **A 主写** | 接近上线前 |

---

## 四、关键路径

```
M0 → M1 → M2 → M3 → M4（MVP）
          ↑
     2.9 sync.py 适配
     （M1 认证完成后可并行开始）
          
     3.1 Three.js 升级
     （M2 末期可并行提前开始）

M4 完成后，M5/M6/M7/M8 可全部并行推进
```

M0 → M4 是必须串行的关键路径，任何一个里程碑卡住都会阻塞后续所有工作。

---

## 五、工作量分布估算

| 里程碑 | A（你） | B（你朋友） |
|---|---|---|
| M0 | 仓库初始化、文档复制、前端复制、FastAPI 脚手架、Kafka 格式抓包、CI 配置（全部） | — |
| M1 | **DDL 设计、PartMaster CRUD、签入签出状态机** | 认证模块、Alembic 脚本、接口文档补充 |
| M2 | **矩阵合成接口、转换回调、sync.py 适配、验证** | PartIteration 接口、文件上传、Kafka 发布 |
| M3 | **Three.js 升级**、viewer 部署、Backbone 下线 | API 适配层、/parts 改造、/bom 改造、iframe 嵌入 |
| M4 | **变更 Schema、ECO 执行项对接 PartMaster** | ECR/ECO 基础模块、前端联调 |
| M5–M11 | **库存管理、Deliverable、项目管理、数据搬运脚本** | **AI 助手**、3D 组件化（AB 共同）、工作流（AB 共同） |

总体：A 约 40%，B 约 60%（B 承接 AI 助手属于 myPDM 专属领域，无法转移，此差距合理）。

---

## 六、风险备忘

| 风险 | 应对 |
|---|---|
| 矩阵合成 Python 移植与 Java 端不一致 | M2 专项验证步骤（2.4），用真实装配体数据逐层对比，不跳过 |
| Kafka 消息格式不兼容 | M0 强制抓包记录（0.8），M2 严格对照文档实现（2.6） |
| ECO 执行触发签入签出竞态 | 执行项使用与普通签入签出同一套 SELECT FOR UPDATE 机制 |
| vault 路径因 UUID 重构而断裂 | vault 路径只用 `{number}/{version}/{iteration}`，与数据库主键解耦 |
| 历史数据搬运丢失关联关系 | M11 脚本维护旧 ID → 新 UUID 映射表，外键跟着换，vault 文件不动 |
