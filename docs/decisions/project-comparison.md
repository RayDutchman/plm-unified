# 两个项目对比与融合路径规划

## 一、项目简介

| | CATIA-Copilot-PLM（本项目） | myPDM |
|---|---|---|
| 基础 | DocDoku PLM 2.6.2 二次开发 | Python + React 全栈自研 |
| 后端 | Java EE 8 / Payara 5 | FastAPI + SQLAlchemy |
| 前端 | Backbone.js（2013 年风格） | React 18 + TypeScript + Vite |
| 数据库 | PostgreSQL + Elasticsearch | PostgreSQL + Redis |
| 部署 | Docker Compose（9 个容器） | Docker Compose（4 个容器） |

---

## 二、各自优势

### 本项目的核心护城河

- **CATIA 深度集成**：通过 COM 接口读取 CATIA 运行时装配关系、位置矩阵、实例信息，直接同步进 PLM，是 Web-first 工具难以复制的能力
- **专业 PLM 数据模型**：三层结构（PartMaster → Revision → Iteration）+ Deliverable 序列号追踪 + PathData 实例级数据，遵循 EIA-649 构型管理理论
- **实时 3D 协同**：WebRTC + 3D 场景完整同步（摄像机、爆炸图、测量、标记），支持多人联合评审
- **企业级基础设施**：Elasticsearch 全文搜索、Kafka 异步 CAD 转换、OIDC/SSO、多工作空间隔离、可视化工作流设计器

### myPDM 的核心优势

- **变更执行闭环**：ECO 执行项逐条追踪（pending/done/failed），变更动作（修改/替换/删除/新增）自动触发版本升级，本项目的变更模块只记录意图不驱动执行
- **现代技术栈**：React 18 + Zustand + Tailwind 的前端体验远优于 Backbone.js；FastAPI 自动生成 OpenAPI 文档
- **功能广度**：库存管理（入库/出库/盘点/移库全流程）、项目管理（甘特图/任务依赖）、AI 助手（DeepSeek + 工具编排，能查询内部 API 并生成报告）
- **权限工程化**：`permissions.json` 单一事实源，代码生成器同时输出前后端权限代码，避免两端不一致

---

## 三、共同缺口

两个项目均未覆盖航空构型管理标准（EIA-649 / GJB 3206B）的以下要求：
- 变更影响的结构化分析表单（偏离许可 / 让步接收）
- 功能/分配/产品三层基线分类
- FCA / PCA 构型审核模块（检查单 + 不一致项管理）
- CSAR 格式化状态报告自动生成

---

## 四、融合路径规划

**原则：不合并代码库，通过 REST API 定义清晰的职责边界。**

```
[CATIA 桌面] ──sync.py──→ [本项目后端] ←──REST API──→ [myPDM 后端]
                               │                              │
                         3D 协同 / CATIA 数据             变更闭环 / 库存 / AI
                               └──────────────┬─────────────┘
                                              │
                                   [myPDM React 前端]（统一入口）
```

**职责划分**：本项目永远是 CATIA 数据的权威入口和 3D 协同的服务提供方；myPDM 前端作为统一操作界面，负责变更执行、库存、项目管理和 AI 问答。

### 第一阶段：数据打通（2–4 周）

1. **整理本项目 REST API** 为 OpenAPI 文档，供 myPDM 对接
2. **认证桥接**：myPDM 增加端点，用本项目 Token 换发 myPDM JWT，实现单点登录
3. **数据同步适配器**：myPDM 新增 `docdoku_adapter`，将本项目的零件 / BOM 数据单向同步为 myPDM 的 Part / Assembly（CATIA 为权威源，myPDM 为只读镜像）
4. **3D 预览嵌入**：在 myPDM 零件详情页通过 iframe 嵌入本项目 3D 查看器

### 第二阶段：功能联动（1–2 个月）

1. **变更执行打通**：myPDM 的 ECO 执行动作（版本升级/替换）调用本项目 REST API 完成，实现"在 myPDM 发起变更 → 本项目数据真正变更"的闭环
2. **3D 协同入口**：myPDM BOM 页增加"进入 3D 协作"按钮，跳转至本项目协同会话
3. **库存联动**：myPDM 库存物料的版本溯源链接到本项目的 Deliverable / 序列号
4. **AI 工具扩展**：myPDM AI 助手增加查询本项目 Elasticsearch 和装配关系的工具，实现跨系统问答

### 第三阶段：深度融合（持续演进）

1. **前端统一**：myPDM React 前端改造为完整主界面，Backbone.js 仅保留管理员工具，最终退役
2. **补足构型管理缺口**：增加三层基线分类、变更影响分析表单、FCA/PCA 审核模块
3. **构型纪实报告**：基于两个系统的综合数据自动生成 CSAR 报告

---

## 五、关键风险

| 风险 | 应对 |
|---|---|
| 数据双写冲突 | 严格定义权威源：CATIA → 本项目 → myPDM 单向流动，myPDM 不写回本项目 BOM 核心数据 |
| 本项目 API 文档缺失 | 第一阶段优先整理，这是一切集成的前提 |
| 认证体系差异 | 第一阶段实现 Token 桥接后，后续各阶段复用同一机制 |
| 两人协作边界 | 数据同步和 ECO 执行改动在 myPDM 侧；3D 协同嵌入接口在本项目侧，各自独立推进 |
