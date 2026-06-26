# plm-unified 文档索引

本目录包含 plm-unified 项目的全部技术文档。

---

## 架构 (`architecture/`)

| 文档 | 说明 |
|------|------|
| [data-model.md](architecture/data-model.md) | 核心数据模型（PartMaster/Revision/Iteration 三层，含 ER 图） |
| [assembly-position.md](architecture/assembly-position.md) | 装配体零件位置机制（cad_instances、矩阵合成、Three.js 渲染） |
| [3d-preview-pipeline.md](architecture/3d-preview-pipeline.md) | STEP→GLB 转换管线（cadquery-ocp、GeometryParser、GLTFLoader） |
| [containers.md](architecture/containers.md) | Docker 服务架构（7 个服务、数据流、volume 说明） |

---

## 集成 (`integration/`)

| 文档 | 说明 |
|------|------|
| [kafka-message-format.md](integration/kafka-message-format.md) | Kafka CONVERT topic 消息格式（Python 实现要点） |
| [catia-sync-protocol.md](integration/catia-sync-protocol.md) | CATIA sync.py 同步协议（骨架，待完善） |

---

## 参考 (`reference/`)

| 文档 | 说明 |
|------|------|
| [rest-api.md](reference/rest-api.md) | DocDoku 原始 REST API 笔记（数据格式参考，非新接口文档） |
| [3d-preview-tuning.md](reference/3d-preview-tuning.md) | 3D 预览参数调整手册（光照、材质、三角化精度） |

---

## 决策 (`decisions/`)

| 文档 | 说明 |
|------|------|
| [project-comparison.md](decisions/project-comparison.md) | CATIA-Copilot-PLM vs myPDM 对比分析 |
| [eco-change-management.md](decisions/eco-change-management.md) | ECR/ECO/ECN 变更管理设计方案（M4 实现参考，来自 myPDM） |
| [mypdm-data-model.md](decisions/mypdm-data-model.md) | myPDM 数据模型字段定义（M4+ 业务迁移字段对照参考） |

---

## 协作 (`collaboration/`)

| 文档 | 说明 |
|------|------|
| [milestones.md](collaboration/milestones.md) | 里程碑计划（M0~M11）与协作约定 |
| [known-issues.md](collaboration/known-issues.md) | 已知问题记录（旧 DocDoku Bug 归档 + 新项目注意事项） |

---

## 开发指南 (`setup/`)

| 文档 | 说明 |
|------|------|
| [local-dev-guide.md](setup/local-dev-guide.md) | 本地开发环境搭建（Docker + 前后端独立开发） |

---

## 快速导航

**我想了解数据库结构** → [architecture/data-model.md](architecture/data-model.md)  
**我想了解装配体 3D 位置如何存储** → [architecture/assembly-position.md](architecture/assembly-position.md)  
**我想了解 CAD 转换管线** → [architecture/3d-preview-pipeline.md](architecture/3d-preview-pipeline.md)  
**我想了解 Kafka 消息格式** → [integration/kafka-message-format.md](integration/kafka-message-format.md)  
**我想搭建本地开发环境** → [setup/local-dev-guide.md](setup/local-dev-guide.md)  
**我想了解项目路线图** → [collaboration/milestones.md](collaboration/milestones.md)  
**我想实现变更管理（M4）** → [decisions/eco-change-management.md](decisions/eco-change-management.md)
