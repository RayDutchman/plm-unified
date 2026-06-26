# 新一代 PLM 系统融合路径规划

> 本文档记录 CATIA-Copilot-PLM 与 myPDM 两个项目的融合设计决策和实施路径。
> 目标：以 DocDoku 的专业 PLM 数据模型和 CATIA 集成能力为基础，以 myPDM 的现代技术栈和业务功能为补充，构建一个统一的新系统。

---

## 设计决策汇总

| 问题 | 决策 |
|---|---|
| 后端框架 | 用 FastAPI 重写，替换 DocDoku Java EE（Payara） |
| 第一步范围 | 只实现零件/BOM/CAD 主线，其余模块后续补齐 |
| 数据库 | 重新设计 Schema（UUID 主键 + 软删除 + updated_at），以 DocDoku 模型为蓝本；需要两类脚本：① Alembic 建库脚本（长期维护）② 一次性数据搬运脚本（上线切换时执行） |
| 零件数据格式 | 统一采用 DocDoku 的 PartMaster/Revision/Iteration 三层模型，抛弃 myPDM 的 Part/Assembly 格式 |
| sync.py | 只换 API 地址，业务逻辑不动 |
| 前端 | 抛弃 Backbone.js，使用 myPDM React 前端 |
| 3D 查看器 | 先 iframe（现有查看器独立运行），长远迁移为 React 组件；Three.js 升级到最新版 |
| 工作流引擎 | 暂缓，后续在 React 前端重新实现可视化设计器 |
| 开发方式 | AI 主导写代码，双方各 review 自己熟悉的部分 |

---

## 目标架构

```
[CATIA 桌面]
     │ sync.py（仅换 API 地址 + JWT 认证）
     ▼
[新统一后端 - FastAPI]
  ├── 零件/BOM/CAD 主线        ← DocDoku 业务逻辑移植
  ├── 签入/签出/迭代状态机      ← DocDoku 业务逻辑移植
  ├── 装配体 + mat4 位置信息    ← DocDoku 业务逻辑移植
  ├── 变更管理闭环（ECR/ECO）   ← myPDM 移植 + 执行项对接 PartMaster
  ├── 库存管理                  ← myPDM 直接移植
  ├── AI 助手                   ← myPDM 直接移植（扩展 Elasticsearch 工具）
  ├── 项目管理                  ← myPDM 直接移植
  ├── Kafka（topic: CONVERT）   ← 保留现有
  ├── Elasticsearch             ← 保留现有
  └── vault 文件存储            ← 保留现有路径格式
     │
[新统一前端 - React（来自 myPDM）]
  └── 3D 协同查看器（先 iframe，后 React 组件）
```

**数据流向（单向，不可逆写）**：
```
CATIA → sync.py → FastAPI 后端 → PostgreSQL
                                    ↑
                           myPDM 前端通过 API 读写
```

---

## 数据库 Schema 重新设计

以 DocDoku 数据模型为语义基准，采用 myPDM 工程风格重建。涉及两类完全不同的工作：

### 类型一：Schema 建库脚本（Alembic，长期维护）

用 Alembic 定义新数据库的表结构。这是**建新库**，不动旧库。

```
旧库：docdokuplm（DocDoku PostgreSQL，开发期间继续运行）
新库：plm_new（新系统的 PostgreSQL，全新建立）
```

Alembic migration 文件描述新库的 DDL（`CREATE TABLE`、`ALTER TABLE` 等），每次部署或 Schema 变更时自动执行，保证版本正确。每加一张新表或改一个字段，就新增一个 Alembic revision 文件。这套脚本随项目长期维护。

### 类型二：历史数据搬运脚本（一次性 Python 脚本）

这是一个**上线切换时执行一次**的 Python 脚本，把旧库 `docdokuplm` 里的现有业务数据读出来，转换格式后写进新库。主要工作：

- 为每条旧记录生成新 UUID，维护旧 ID → 新 UUID 的映射表（外键跟着换）
- vault 文件路径使用零件编号和版本号（非数据库主键），**vault 文件本身不需要移动**
- 脚本设计为幂等，可重跑（先清空目标表再插入）

开发阶段旧库数据不多，这个脚本可以推迟到接近上线前再写，不影响主线开发。

### 新表结构对照

| DocDoku 原表 | 新表名 | 主要变更 |
|---|---|---|
| `PARTMASTER` | `part_masters` | 复合主键 → UUID；加 `deleted_at`, `updated_at` |
| `PARTREVISION` | `part_revisions` | 复合主键 → UUID；外键引用 `part_masters.id` |
| `PARTITERATION` | `part_iterations` | 复合主键 → UUID；外键引用 `part_revisions.id` |
| `PARTUSAGELINK` | `part_usage_links` | int PK → UUID；关联 `part_iterations.id`（components） |
| `CADINSTANCE` | `cad_instances` | int PK → UUID；保留 tx/ty/tz/rx/ry/rz/m00~m22/rotationType |
| `GEOMETRY` | `geometries` | 继承改为独立表；保留 quality + 包围盒字段 |
| `BINARYRESOURCE` | `binary_resources` | fullName PK → UUID；保留 vault 路径字段 |
| `CHANGEISSUE` | `change_issues` | int PK → UUID；加 status_logs JSONB |
| `CHANGEREQUEST` | `change_requests` | int PK → UUID |
| `CHANGEORDER` | `change_orders` | int PK → UUID |
| —（新增） | `eco_execution_items` | 来自 myPDM，ECO 执行项逐条追踪 |
| —（新增） | `inventory_*` | 来自 myPDM，库存模块全套 |
| —（新增） | `projects`, `project_tasks` | 来自 myPDM，项目管理 |

**关键约束**：
- vault 路径格式 `Workspace_X/parts/{number}/{version}/{iteration}/nativecad/` 保持不变，不依赖内部 UUID
- 历史数据搬运脚本从旧库 `docdokuplm` 读取数据，维护旧 ID → 新 UUID 映射，幂等可重跑；开发阶段可推迟实现

---

## 阶段 0：准备与设计（约 1–2 周）

**目标**：在写任何业务代码之前，确定数据库 Schema 和 API 契约，让双方可并行开发。

### 任务

**0.1 确认新 Schema**
- 你（熟悉 DocDoku）：确认新 Schema 的业务语义是否完整，特别是 `cad_instances`、`part_usage_links`、`geometries` 的关联关系
- 你朋友：设计最终 SQL DDL，搭建 FastAPI 项目脚手架（参考 myPDM 目录结构）

**0.2 梳理 Kafka 消息格式**
- 抓包记录现有 DocDoku 发往 topic `CONVERT` 的消息结构，写入设计文档
- Python 端 Kafka 客户端（`aiokafka`）必须发送完全相同的格式

**0.3 确认 API 路径风格**
- 保留 DocDoku 路径风格：`/api/workspaces/{ws}/parts/{number}-{version}`
- sync.py 只需更换 host 和认证方式（Basic Auth → JWT）

**0.4 搭建 Alembic 建库脚本框架**
- 你朋友搭框架，定义第一批核心表的 DDL
- 你 review 表结构的业务语义完整性（特别是 `cad_instances`、`part_usage_links` 的关联关系）
- 历史数据搬运脚本（类型二）在开发阶段先不做，接近上线前再补

---

## 阶段 1：FastAPI 核心主线（约 4–6 周）

**目标**：新 FastAPI 后端替代 DocDoku Java 后端，覆盖零件/BOM/CAD 全链路。

**分工**：你朋友主写；你 review 签入签出状态机、矩阵合成逻辑、转换回调逻辑。

### 1.1 基础设施

- FastAPI + SQLAlchemy 2.0 项目结构
- Alembic 版本化迁移（即类型一建库脚本，替代 myPDM 的启动自动检测方式，避免生产风险）
- JWT 认证（复用 myPDM 的 `auth.py`）
- Docker：新后端容器替换 `back`（Payara），保留 db/es/kafka/zookeeper/conversion 容器不动

### 1.2 零件主线 API（按优先级）

| 优先级 | 接口 | 说明 |
|---|---|---|
| P0 | `POST /api/workspaces/{ws}/parts` | 创建零件 |
| P0 | `GET /api/workspaces/{ws}/parts/{number}-{version}` | 获取零件详情 |
| P0 | `PUT .../versions/{ver}/checkout` | 签出 |
| P0 | `PUT .../versions/{ver}/checkin` | 签入 |
| P0 | `PUT .../versions/{ver}/undocheckout` | 撤销签出 |
| P0 | `PUT .../versions/{ver}/iterations/{iter}` | 更新迭代（含 components + cadInstances） |
| P1 | `GET /api/workspaces/{ws}/parts` | 列表查询 |
| P1 | `PUT .../versions/{ver}/newversion` | 创建新版本 |
| P1 | `POST .../iterations/{iter}/nativecad` | 上传 CAD 文件 |
| P1 | `GET .../iterations/{iter}/conversion` | 查询转换状态 |
| P1 | `PUT .../iterations/{iter}/conversion` | 转换回调（conversion 容器调用） |

### 1.3 装配体与位置信息（重点 review）

这是 3D 渲染正确性的关键：

- `PUT .../iterations/{iter}` 接收 `components[].cadInstances[]`，写入 `part_usage_links` + `cad_instances`
- 保留 ANGLE（tx/ty/tz + rx/ry/rz）和 MATRIX（tx/ty/tz + 3x3 矩阵）两种旋转模式
- `GET /api/workspaces/{ws}/products/{ciId}/instances`：递归遍历装配树，层层累乘变换矩阵，输出 16 元素全局 mat4 数组，逻辑必须与原 `InstanceBodyWriterTools.java` 完全一致
- `amount` 字段必须正确写入（历史 bug，已记录）

**验证方式**：阶段 1 完成后，用现有 DocDoku 的实际零件数据对比 Java 和 Python 两端的矩阵输出，逐层验证。

### 1.4 Kafka 集成

- 使用 `aiokafka`
- 上传 CAD 文件后发布消息到 topic `CONVERT`，格式与现有 conversion 容器完全兼容
- conversion 容器回调接口保持兼容，不修改 conversion 服务

### 1.5 签入签出并发保护

- 使用 `SELECT FOR UPDATE` 防止同一零件被多人同时签出
- 对应 DocDoku 原有的数据库行锁机制

---

## 阶段 2：前端切换（约 2–4 周）

**目标**：myPDM React 前端对接新后端，用户可用新前端完成零件和 BOM 的全部操作。

**分工**：你朋友主写前端改造；你 review 3D 相关部分和 Three.js 升级。

### 2.1 API 适配层

- `apiService` 中零件/BOM 调用切换到新 FastAPI
- 统一 JWT Token，前端只维护一套认证
- myPDM 的 Part/Assembly 数据模型从前端彻底移除

### 2.2 零件和 BOM 页面改造

- `/parts`：展示 PartMaster 列表，支持展开查看各 Revision 和 Iteration
- `/bom`：展示产品装配树（ConfigurationItem 为根节点）
- 签入/签出状态标识、版本状态（WIP/RELEASED/OBSOLETE）

### 2.3 3D 查看器嵌入（iframe 阶段）

- 现有 Backbone.js 3D 查看器保留为独立静态服务（单独 nginx 容器）
- myPDM 前端零件详情页通过 `<iframe>` 嵌入，传入 JWT Token 和零件路径参数
- **Three.js 升级**：在现有查看器代码中升级 Three.js 到最新版（r168+），处理 breaking change，由你 review

### 2.4 Backbone.js 下线

- `front` 容器（Backbone.js 主界面）下线
- 原 `front` nginx 改为仅服务 3D 查看器静态页面（临时，直到阶段 5 完成 React 组件化）

---

## 阶段 3：变更管理闭环（约 3–4 周）

**目标**：完整的 ECR/ECO 流程，ECO 执行项驱动 PartMaster 数据的实际版本操作。

**分工**：你朋友主写（基于 myPDM ECR/ECO）；你 review ECO 执行时的版本操作是否符合 DocDoku 业务规则。

### 3.1 变更模块迁移

将 myPDM 的 ECR/ECO 路由、Schema、CRUD 迁移到新 FastAPI。

### 3.2 ECO 执行项对接 PartMaster

| 执行动作 | 实现方式 |
|---|---|
| 修改零件属性 | 签出 → 更新 PartIteration → 签入 |
| 版本升级（A→B） | 调用 `newversion` 接口，创建新 PartRevision |
| 替换子件 | 修改 `part_usage_links.component` 指向新 PartMaster |
| 删除子件 | 从 `part_iterations.components` 移除对应 PartUsageLink |
| 新增子件 | 向 `part_iterations.components` 添加新 PartUsageLink |

每条执行项完成后状态更新为 `done`，失败更新为 `failed` 并记录原因。

### 3.3 前端

myPDM `/ec` 页面直接复用，调整 API 调用地址。

---

## 阶段 4：扩展功能迁移（按需推进，各子任务独立）

### 4.1 库存管理（你朋友主写）
- 直接移植 myPDM 库存模块
- 物料主数据从 PartMaster 同步
- 库存台账、入库/出库/盘点/移库单据
- 版本溯源链接到 PartRevision

### 4.2 AI 助手（你朋友主写）
- 直接移植 myPDM AI 模块
- 扩展工具集：增加查询 Elasticsearch 的工具
- 增加查询装配树和 mat4 位置信息的工具
- 增加查询 Deliverable/序列号追踪的工具

### 4.3 项目管理（你朋友主写）
- 直接移植 myPDM 项目管理模块
- 与变更里程碑关联

### 4.4 Deliverable / 序列号追踪（你主写）
- 将 DocDoku 的 ProductInstance/PathData 概念迁移到新 FastAPI
- 前端展示序列号视图（基于 myPDM Deliverable 页面改造）

### 4.5 工作流引擎（暂缓）
- 在 React 前端重新实现可视化工作流设计器
- 后端实现工作流模板存储和状态机执行
- 启动时机：阶段 4 其他模块完成后评估资源

---

## 阶段 5：3D 查看器 React 组件化（长期目标）

**目标**：将 3D 查看器从 iframe 升级为原生 React 组件，彻底融入统一前端。

**分工**：两人协作；3D 渲染逻辑和 mat4 矩阵处理由你重点 review。

### 5.1 组件化范围

| 功能 | 实现方式 |
|---|---|
| GLB 模型加载与渲染 | `@react-three/fiber` + `@react-three/drei` 的 `useGLTF` |
| 装配树 + 位置矩阵 | 从 `/products/{ciId}/instances` 取全局 mat4，创建 Object3D 节点 |
| 摄像机控制 | `@react-three/drei` 的 `OrbitControls` |
| 爆炸视图 | 沿法向量方向偏移各节点 |
| 剖切视图 | Three.js `Plane` + `Clipping` |
| 测量工具 | Raycaster 拾取 + 两点距离计算 |
| 3D 标记 | `Sprite` 或 `Html`（@react-three/drei） |
| 实时协同同步 | WebSocket 同步摄像机参数、可见性状态 |
| 截图 | `renderer.domElement.toDataURL()` |

### 5.2 iframe 退役

React 3D 组件稳定后，移除 iframe，独立的 3D 查看器 nginx 服务下线。

---

## 关键风险与应对

| 风险 | 说明 | 应对 |
|---|---|---|
| **矩阵合成逻辑移植** | `InstanceBodyWriterTools.java` 的递归矩阵累乘是 3D 正确性的关键 | 阶段 1 后用实际数据对比 Java/Python 两端输出，逐层验证 |
| **Kafka 消息格式兼容** | conversion 容器期望特定格式，Python 端必须完全兼容 | 阶段 0 先抓包记录现有消息格式，写入设计文档 |
| **签入签出并发** | 多人同时操作同一零件的竞态条件 | FastAPI 中用 `SELECT FOR UPDATE` 实现行锁 |
| **vault 路径与 UUID 解耦** | 新 UUID 主键不能影响 vault 路径格式 | vault 路径使用 `{number}/{version}/{iteration}` 而非内部 UUID |
| **Elasticsearch 索引重建** | 新表结构需重新定义 index mapping | 阶段 1 先降级为 DB LIKE 查询，Elasticsearch 作为 P2 补齐 |
| **ECO 执行逻辑重写** | myPDM ECO 原来操作自己的 Part 表，改为操作 PartMaster 逻辑不同 | 阶段 3 前对齐 DocDoku 版本操作的完整规则，特别是签入签出状态机 |

---

## 分工总览

| 阶段 | 你负责 | 你朋友负责 |
|---|---|---|
| **阶段 0** | 确认 Schema 语义；梳理 Kafka 消息格式；确认 API 路径风格 | 设计 SQL DDL；搭建 FastAPI 脚手架；搭建 Alembic 建库脚本框架 |
| **阶段 1** | Review 签入签出状态机；Review 矩阵合成逻辑；Review 转换回调 | 实现所有 FastAPI 路由和 SQLAlchemy 模型；Kafka 集成 |
| **阶段 2** | Review 3D iframe 嵌入；Three.js 版本升级 | 前端 API 适配层；零件/BOM 页面改造；Backbone.js 下线 |
| **阶段 3** | Review ECO 执行的版本操作规则 | ECR/ECO 迁移；执行项对接 PartMaster |
| **阶段 4** | Deliverable / 序列号追踪 | 库存、AI、项目管理移植 |
| **阶段 5** | Review mat4 矩阵/3D 渲染逻辑；WebSocket 协同 | React 3D 组件化；iframe 退役 |
