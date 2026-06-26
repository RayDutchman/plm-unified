# plm-unified

新一代 PLM 系统：以 DocDoku PLM 数据模型为基础，FastAPI 后端 + React 前端，融合 CATIA 深度集成与现代化 PDM 业务功能。

## 项目背景

本项目融合了两个项目的核心优势：

- **CATIA-Copilot-PLM**：DocDoku PLM 的深度二次开发，专业的 PLM 数据模型（PartMaster/Revision/Iteration）、CATIA 运行时集成、实时 3D 协同
- **myPDM**：现代化 FastAPI + React 技术栈，完整的变更执行闭环（ECR/ECO）、库存管理、AI 助手

详细设计见 [`docs/fusion-roadmap.md`](docs/fusion-roadmap.md)。

## 目录结构

```
/backend      FastAPI 后端
/frontend     React 前端（来自 myPDM）
/conversion   CAD 转换服务（来自 CATIA-Copilot-PLM，不改动）
/docker       Docker Compose 编排
/docs         设计文档
/scripts      工具脚本（sync.py 等）
```

## 快速启动

```bash
docker compose up -d
```

后端健康检查：`http://localhost:8000/health`

## 协作方式

详见 [`CONTRIBUTING.md`](CONTRIBUTING.md) 和 [`docs/collaboration-and-milestones.md`](docs/collaboration-and-milestones.md)。
