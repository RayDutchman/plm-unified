# 数据模型设计

> plm-unified 核心数据模型文档。以 DocDoku PartMaster/Revision/Iteration 三层模型为基础，用 PostgreSQL 重新实现。  
> 完整 DDL 见 `backend/sql/init.sql`。

---

## 一、设计原则

| 原则 | 说明 |
|------|------|
| UUID 主键 | 所有表使用 `uuid_generate_v4()` 作为主键，避免自增 ID 泄露序列信息 |
| 软删除 | `part_masters`、`part_revisions`、`users`、`workspaces` 含 `deleted_at` 字段，删除只打标记 |
| `updated_at` 自动维护 | 所有有 `updated_at` 的表挂载触发器，UPDATE 时自动更新 |
| 外键 + ON DELETE | 关联关系均有显式外键约束，子记录策略为 CASCADE 或 RESTRICT，防止孤儿数据 |
| 不可空约束 | 必填业务字段均标 `NOT NULL`，避免数据不一致 |

---

## 二、实体关系概览

```
workspaces
  └──1:N── part_masters（零件主数据，workspace_id + number 唯一）
                └──1:N── part_revisions（版本 A/B/C…，状态机 WIP→RELEASED→OBSOLETE）
                              └──1:N── part_iterations（迭代 1/2/3…，签入后冻结）
                                            ├── native_cad_file_id → binary_resources（原生 CAD 文件）
                                            ├──1:N── geometries（LOD 几何体，含包围盒）
                                            │           └── binary_resource_id → binary_resources
                                            └──1:N── part_usage_links（装配 BOM）
                                                          ├── component_master_id → part_masters
                                                          └──1:N── cad_instances（位置/变换矩阵）

users（登录用户，workspace_id 关联）
binary_resources（文件元数据，full_name 为 vault 路径键）
```

---

## 三、核心表说明

### 3.1 `part_masters`（零件主数据）

对应 DocDoku `PartMaster`。

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID PK | 主键 |
| `workspace_id` | UUID FK→workspaces | 所属工作空间 |
| `number` | VARCHAR(100) | 零件编号，工作空间内唯一 |
| `name` | VARCHAR(255) | 零件名称 |
| `type` | VARCHAR(50) | 零件类型（可选） |
| `standard_part` | BOOLEAN | 是否标准件（外购/通用件） |
| `author_id` | UUID FK→users | 创建者 |
| `deleted_at` | TIMESTAMPTZ | 软删除标记 |

**唯一约束：** `(workspace_id, number)`

---

### 3.2 `part_revisions`（零件版本）

对应 DocDoku `PartRevision`。

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID PK | 主键 |
| `part_master_id` | UUID FK→part_masters | 所属零件 |
| `version` | VARCHAR(10) | 版本号，字母递增（A/B/C…） |
| `status` | ENUM | `WIP` / `RELEASED` / `OBSOLETE` |
| `description` | TEXT | 版本描述 |
| `checkout_user_id` | UUID FK→users | 当前签出用户（NULL=未签出） |
| `checkout_date` | TIMESTAMPTZ | 签出时间 |
| `released_by_id` / `released_at` | UUID / TIMESTAMPTZ | 发布记录 |
| `obsoleted_by_id` / `obsoleted_at` | UUID / TIMESTAMPTZ | 废弃记录 |
| `deleted_at` | TIMESTAMPTZ | 软删除标记 |

**唯一约束：** `(part_master_id, version)`

**状态机：**
```
WIP ──（release）──→ RELEASED ──（obsolete）──→ OBSOLETE
 ↑                      │
 └──（新版本升版）       │（不可回退，RELEASED 是终态之一）
```

---

### 3.3 `part_iterations`（零件迭代）

对应 DocDoku `PartIteration`。每次签出+修改+签入产生一个新迭代。

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID PK | 主键 |
| `part_revision_id` | UUID FK→part_revisions | 所属版本 |
| `iteration` | INTEGER | 迭代号，从 1 递增，CHECK > 0 |
| `iteration_note` | TEXT | 本次迭代备注 |
| `native_cad_file_id` | UUID FK→binary_resources | 原生 CAD 文件（可 NULL） |
| `check_in_date` | TIMESTAMPTZ | 签入时间（NULL=当前 WIP 迭代） |
| `author_id` | UUID FK→users | 创建者 |

**唯一约束：** `(part_revision_id, iteration)`

---

### 3.4 `binary_resources`（二进制资源）

对应 DocDoku `BinaryResource`。仅存储元数据，实际文件存储在 vault（Docker volume）。

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID PK | 主键 |
| `full_name` | VARCHAR(500) UNIQUE | vault 路径键（全局唯一） |
| `content_length` | BIGINT | 文件大小（字节） |
| `last_modified` | TIMESTAMPTZ | 最后修改时间 |

**full_name 路径格式：**
```
{workspace}/parts/{number}/{version}/{iteration}/nativecad/{filename}   # 原生 CAD 文件
{workspace}/parts/{number}/{version}/{iteration}/geometries/{filename}  # 几何体（GLB）
```

---

### 3.5 `geometries`（几何体）

对应 DocDoku `Geometry`（继承 `BinaryResource`）。每个迭代可有多个不同 LOD 的几何体。

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID PK | 主键 |
| `iteration_id` | UUID FK→part_iterations | 所属迭代 |
| `binary_resource_id` | UUID FK→binary_resources | 实际文件 |
| `quality` | INTEGER | LOD 质量等级，0=最高，越大越低 |
| `x_min/y_min/z_min` | DOUBLE PRECISION | 包围盒最小值（毫米） |
| `x_max/y_max/z_max` | DOUBLE PRECISION | 包围盒最大值（毫米） |

---

### 3.6 `part_usage_links`（装配 BOM）

对应 DocDoku `PartUsageLink`。表达"父迭代使用子零件"的关系。

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID PK | 主键 |
| `parent_iteration_id` | UUID FK→part_iterations | 父装配体迭代 |
| `component_master_id` | UUID FK→part_masters | 子零件主数据 |
| `amount` | DOUBLE PRECISION | 用量 |
| `unit` | VARCHAR(20) | 单位（ea/mm 等） |
| `optional` | BOOLEAN | 是否可选件 |
| `order` | INTEGER | 在父装配体中的排序 |
| `comment` | TEXT | 备注 |

**注意：** 子零件引用的是 `part_masters`（零件主数据），不是特定版本或迭代。具体使用哪个版本由配置规格（configSpec）决定，默认使用 latest RELEASED 版本。

---

### 3.7 `cad_instances`（CAD 实例/位置）

对应 DocDoku `CADInstance`。一个 `PartUsageLink` 可有多个 `CADInstance`，表示同一子件多次出现在不同位置。

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | UUID PK | 主键 |
| `usage_link_id` | UUID FK→part_usage_links | 所属使用关系 |
| `tx/ty/tz` | DOUBLE PRECISION | 平移向量（毫米） |
| `rotation_type` | ENUM | `ANGLE`（欧拉角）或 `MATRIX`（旋转矩阵） |
| `rx/ry/rz` | DOUBLE PRECISION | ANGLE 模式：欧拉角（弧度） |
| `m00..m22` | DOUBLE PRECISION | MATRIX 模式：3×3 旋转矩阵（列优先存储） |
| `order` | INTEGER | 在 usage_link 中的排序 |

**CHECK 约束：**
- ANGLE 模式：`rx/ry/rz` 不得为 NULL
- MATRIX 模式：`m00..m22` 全部不得为 NULL

详细的位置机制说明见 [`assembly-position.md`](./assembly-position.md)。

---

## 四、与 myPDM 数据模型的对比

| 维度 | plm-unified（DocDoku 模型） | myPDM 模型 |
|------|---------------------------|-----------|
| 零件标识 | `workspace_id + number` | `code + version` 联合唯一 |
| 版本管理 | 独立的 PartRevision 层（A/B/C…） | `version` 字段内嵌在 parts 表 |
| 修改历史 | PartIteration（每次签入一条记录） | `revisions` JSONB 字段 |
| 装配关系 | part_usage_links（独立表） | bom_items（独立表） |
| 位置信息 | cad_instances（支持矩阵/欧拉角） | 无（myPDM 不含 3D 位置） |
| 几何文件 | binary_resources + geometries | 附件通过 document_attachments |
| 签出锁定 | checkout_user_id + checkout_date | 无签出机制 |

myPDM 的业务功能字段（ECO 变更、库存、配置管理等）将在 M4+ 阶段以独立表的形式扩展到 plm-unified。  
参考文档：[`decisions/eco-change-management.md`](../decisions/eco-change-management.md)

---

## 五、索引策略

| 索引 | 用途 |
|------|------|
| `idx_part_masters_workspace` | 按工作空间列举零件 |
| `idx_part_masters_number` | 按编号搜索（含软删除过滤） |
| `idx_part_revisions_master` | 按零件查版本列表 |
| `idx_part_revisions_checkout` | 查当前已签出的版本（并发保护） |
| `idx_part_revisions_status` | 按状态筛选 |
| `idx_part_iterations_revision` | 按版本查迭代列表 |
| `idx_geometries_iteration` | 按迭代查几何体 |
| `idx_part_usage_links_parent` | 按父迭代查 BOM 子项 |
| `idx_part_usage_links_component` | Where-Used 反查（子零件→父装配体） |
| `idx_cad_instances_usage_link` | 按使用关系查位置实例 |
| `idx_binary_resources_fullname` | vault 路径前缀查询 |

---

*文档版本：M1.1 | 最后更新：2026-06-26*
