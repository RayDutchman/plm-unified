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

| # | 行动项 | 负责 | 串/并 |
|---|---|---|---|
| 2.1 | 实现 PartIteration 更新接口（接收 `components[].cadInstances[]`，写入 `part_usage_links` + `cad_instances`，保留 ANGLE/MATRIX 两种旋转模式） | B | 串行起点 |
| 2.2 | A review cadInstances 写入逻辑，对照 DocDoku 原始数据验证字段映射 | A | → 2.1 |
| 2.3 | 实现矩阵合成接口（`GET /products/{ciId}/instances`）：用 Python 实现递归装配树遍历，层层累乘 mat4，输出 16 元素全局矩阵数组 | **A 主写** | ‖ 2.1（可并行设计，等 2.1 数据结构确定后写实现） |
| 2.4 | 用现有 DocDoku 实际零件数据对比验证：Java 端与 Python 端矩阵输出逐层比对 | A | → 2.3 |
| 2.5 | 实现 CAD 文件上传接口（`POST .../nativecad`），写入 vault，路径格式保持 `Workspace_X/parts/{number}/{version}/{iteration}/nativecad/` | B | ‖ 2.3 |
| 2.6 | 实现 Kafka 消息发布（`aiokafka`），格式严格对照 `/docs/integration/kafka-message-format.md` | B | → 2.5 |
| 2.7 | 实现转换回调接口（`PUT .../conversion`）：查找真正 pending 的 Conversion 记录（不能用 getLastIteration），写入 geometry 路径 | **A 主写** | → 2.6 |
| 2.8 | 实现转换状态查询接口（`GET .../conversion`，返回 `{pending, succeed}`） | A | ‖ 2.7 |
| 2.9 | 适配 sync.py：更换 API base URL，将 Basic Auth 改为 JWT | A | → M1 认证完成即可开始 |
| 2.10 | 写 M2 验收测试脚本（端到端：sync.py 同步装配体 → 上传 STP → 轮询转换状态 → 查询 instances 接口） | AB | → 2.8 |

**✅ M2 达成条件**：验收测试全部通过——从 CATIA 通过 sync.py 同步一个多层装配体，转换完成后 `instances` 接口返回的全局 mat4 与 DocDoku Java 端输出逐层一致，在旧 3D 查看器中渲染位置正确。

---

### M3：前端切换 + 3D 查看器 iframe

**M2 完成后启动。**

| # | 行动项 | 负责 | 串/并 |
|---|---|---|---|
| 3.1 | 升级现有 3D 查看器 Three.js 到最新版（r168+），处理 breaking change，确保旧功能不退化 | A | 串行起点（可与 M2 末期并行提前开始） |
| 3.2 | 将升级后的 3D 查看器部署为独立静态服务（新增 `viewer` nginx 容器） | A | → 3.1 |
| 3.3 | React 前端 API 适配层：零件/BOM 调用全部切换到新 FastAPI，移除 myPDM Part/Assembly 数据模型 | B | → M2 完成 |
| 3.4 | 改造 `/parts` 页面：展示 PartMaster 列表，支持展开查看各 Revision 和 Iteration，显示签出状态 | B | → 3.3 |
| 3.5 | 改造 `/bom` 页面：展示装配树（ConfigurationItem 为根节点），显示版本状态（WIP/RELEASED/OBSOLETE） | B | ‖ 3.4 |
| 3.6 | 在零件详情页嵌入 3D 查看器 iframe（传入 JWT Token + 零件路径参数） | B | → 3.2 & 3.4 |
| 3.7 | 下线 Backbone.js `front` 容器，从 docker-compose 移除 | A | → 3.6 测试通过后 |
| 3.8 | 写 M3 验收测试（前端 E2E：创建零件→BOM 查看→3D 预览完整流程） | AB | → 3.6 |

**✅ M3 达成条件**：验收测试全部通过——用户完全通过 React 前端完成零件创建、BOM 查看、3D 预览，Backbone.js 前端不再需要，旧 `front` 容器已下线。

---

### M4：变更管理闭环（MVP）

**M3 完成后启动。M4 达成即进入 MVP 状态。**

| # | 行动项 | 负责 | 串/并 |
|---|---|---|---|
| 4.1 | 设计变更管理新 Schema（`change_issues`、`change_requests`、`change_orders`、`eco_execution_items`），写 Alembic migration | **A 主写** | 串行起点 |
| 4.2 | B review Schema，确认 `eco_execution_items` 与 myPDM 原有字段的映射 | B | → 4.1 |
| 4.3 | 实现 ECR 模块（CRUD、审批流、状态机：draft→submitted→approved→closed） | B | → 4.2 |
| 4.4 | 实现 ECO 基础模块（CRUD、审批流）及执行状态机（draft→submitted→approved→executing→executed→closed） | B | ‖ 4.3 |
| 4.5 | 实现 ECO 执行项对接 PartMaster（5 种执行动作，每项完成后写回 done/failed 状态） | **A 主写** | → 4.4 |
| 4.6 | B review ECO 执行逻辑，确认与 myPDM 原有执行框架兼容 | B | → 4.5 |
| 4.7 | 前端 `/ec` 页面联调（直接复用 myPDM `/ec`，调整 API 地址） | B | → 4.5 |
| 4.8 | 写 M4 验收测试（端到端：提交 ECR→审批→创建 ECO→执行版本升级→执行项 done→新版本可查） | AB | → 4.7 |

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
