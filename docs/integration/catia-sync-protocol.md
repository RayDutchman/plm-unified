# CATIA 同步协议

> 记录 CATIA Copilot（`scripts/sync.py`）与 plm-unified FastAPI 后端之间的数据同步协议。  
> 这是 CATIA 数据进入 PLM 系统的唯一入口。

---

## 一、概述

`sync.py` 是一个 Python 脚本，运行在 CATIA 所在的 Windows 机器上。它通过 CATIA Automation API（COM）读取当前打开的装配体，并通过 REST API 将数据推送到后端。

```
CATIA V5/V6（Windows）
    │
    ▼ COM API（win32com）
    │   读取：Part Number、版本、位置矩阵、BOM 层级
    │
    ▼ sync.py
    │   整理数据，调用 REST API
    │
    ▼ FastAPI backend（HTTP REST）
        写入：part_masters, part_revisions, part_iterations,
              part_usage_links, cad_instances, binary_resources
```

---

## 二、同步步骤

同步一个装配体的完整顺序（深度优先，叶子零件优先）：

```
1. POST /api/auth/login              → 获取 JWT
2. 对每个零件（深度优先遍历，叶子→根）：
   a. POST /api/workspaces/{ws}/parts          → 创建零件（若已存在则跳过 / 409）
   b. POST .../versions/{ver}/checkouts        → 签出（若未签出）
   c. PUT  .../iterations/{iter}               → 写入 BOM + cadInstances
   d. PUT  /api/files/.../nativecad            → 上传 .stp 文件（若有）
   e. GET  .../conversion                      → 轮询转换状态（pending=false）
   f. PUT  .../versions/{ver}/checkins         → 签入
3. POST /api/auth/logout
```

---

## 三、消息格式（Kafka CONVERT topic）

详细格式见 [`integration/kafka-message-format.md`](../integration/kafka-message-format.md)。

| 字段 | 说明 |
|------|------|
| 消息 key | `{workspaceId}/{partNumber}/{version}-{iteration}` |
| `partIterationKey` | 嵌套对象，含 workspace/number/version/iteration |
| `binaryResource` | `fullName`（vault 路径）、`contentLength`、`lastModified` |
| `userToken` | 用于回调鉴权的 JWT |

---

## 四、已知约束

| 约束 | 说明 |
|------|------|
| 单向同步 | CATIA → PLM，PLM 不写回 CATIA |
| 签出串行 | 同一零件的"签出→上传→等转换→签入"必须串行，不同零件可并行 |
| 文件名大小写 | vault 路径大小写敏感，文件名必须与 STEP 内部引用一致 |
| `acks=0` | Kafka Producer 当前配置为 fire-and-forget，broker 不可用时消息可能丢失（见 known-issues.md BUG-14） |
| CATIA 格式限制 | `.CATPart`/`.CATProduct` 无法直接转换，需先在 CATIA 内导出为 `.step` |

---

## 五、待完善

> 本文档为骨架，sync.py 实现细节待补充。

- [ ] sync.py 完整调用序列（含重试逻辑）
- [ ] CATIA COM API 字段读取清单（PartNumber、版本、矩阵、BOM 层级）
- [ ] 并行上传的并发控制实现
- [ ] 增量同步（只同步有变化的零件）
- [ ] 错误处理与日志格式

---

*文档版本：骨架 | 最后更新：2026-06-26*
