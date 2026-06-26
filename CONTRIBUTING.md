# 贡献指南

本文档是两人协作开发 plm-unified 的约定，详细内容参见 [`docs/collaboration/milestones.md`](docs/collaboration/milestones.md)。

---

## 分支策略

```
main       ← 只接受 PR 合并，始终保持可运行状态（对应里程碑节点）
dev        ← 集成分支，功能完成后先合并到 dev 联调
feat/xxx   ← 功能分支，如 feat/fastapi-part-api
fix/xxx    ← Bug 修复分支
```

工作流：`feat/xxx → PR → dev（联调通过）→ PR → main（里程碑达成）`

- AI 生成的代码同样必须经过 PR 流程，不直接推送 `dev` 或 `main`
- 每个 PR 至少另一方 review 并 approve 后才可合并

---

## 提交信息格式

遵循 [Conventional Commits](https://www.conventionalcommits.org/)：

```
<类型>(<范围>): <简短描述>
```

| 类型 | 用途 |
|---|---|
| `feat` | 新功能 |
| `fix` | Bug 修复 |
| `refactor` | 重构 |
| `test` | 测试 |
| `docs` | 文档 |
| `chore` | 构建/依赖/配置 |
| `perf` | 性能优化 |

范围示例：`part-api`、`bom`、`3d-viewer`、`ecr`、`eco`、`inventory`、`frontend`、`docker`、`sync`

示例：
```
feat(part-api): 实现签入签出状态机

使用 SELECT FOR UPDATE 防止并发签出。
对应 DocDoku CheckInManager / CheckOutManager 的业务逻辑。
```

---

## 命名规范

| 类型 | 规范 | 示例 |
|---|---|---|
| Python 变量/函数 | `snake_case` | `part_master_id`, `get_checkout_status()` |
| Python 类 | `PascalCase` | `PartMasterService` |
| Python 常量 | `UPPER_SNAKE_CASE` | `KAFKA_TOPIC_CONVERT` |
| TypeScript 变量/函数 | `camelCase` | `partMasterId` |
| TypeScript 组件/类 | `PascalCase` | `PartDetailPanel` |
| 数据库表名 | `snake_case` 复数 | `part_masters` |
| 数据库字段名 | `snake_case` | `created_at`, `rotation_type` |
| Git 分支名 | `feat/kebab-case` | `feat/part-checkout-api` |

---

## 注释规范

- 代码注释使用**中文**
- 复杂业务逻辑必须注明来源（如"对应 DocDoku InstanceBodyWriterTools.java"）
