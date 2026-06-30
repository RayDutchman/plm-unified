# PLM Unified 数据库模型参考

> 最后更新：2026-06-30  
> 表总数：49 张业务表 + 1 张 alembic_version

---

## 一、基础层（3 表）

### workspaces
工作空间，数据隔离顶层。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | uuid | PK | |
| name | varchar(100) | UNIQUE, NOT NULL | 工作空间标识 |
| description | text | | |
| created_at | timestamptz | NOT NULL | |
| updated_at | timestamptz | NOT NULL | |
| deleted_at | timestamptz | | 软删除 |

### users
用户账号。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | uuid | PK | |
| workspace_id | uuid | FK→workspaces, NOT NULL | 归属空间 |
| username | varchar(64) | UNIQUE, NOT NULL | 登录名 |
| password_hash | varchar(255) | NOT NULL | bcrypt |
| real_name | varchar(64) | NOT NULL | 显示名 |
| role | varchar(32) | NOT NULL | admin/engineer/production/guest |
| department | varchar(128) | | 部门 |
| phone | varchar(32) | | 电话 |
| status | varchar(32) | NOT NULL | active/disabled |
| created_at | timestamptz | NOT NULL | |
| updated_at | timestamptz | NOT NULL | |
| deleted_at | timestamptz | | 软删除 |

### user_groups / user_group_members
用户组与成员关联。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | uuid | PK | |
| name | varchar(64) | UNIQUE, NOT NULL | 组名 |
| description | text | | |
| created_at | timestamptz | NOT NULL | |
| updated_at | timestamptz | NOT NULL | |

user_group_members：`user_id (FK→users)` + `group_id (FK→user_groups)` 联合主键。

---

## 二、零件三层模型 — 对标 DocDoku（3 表）

### part_masters
零件主数据，workspace_id + number 唯一。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | uuid | PK | |
| workspace_id | uuid | FK→workspaces, NOT NULL | |
| number | varchar(100) | NOT NULL, UNIQUE(ws+num) | 零件编号 |
| name | varchar(255) | NOT NULL | 零件名称 |
| type | varchar(50) | | 零件类型 |
| standard_part | boolean | NOT NULL, DEFAULT false | 是否标准件 |
| author_id | uuid | FK→users, NOT NULL | 创建者 |
| created_at | timestamptz | NOT NULL | |
| updated_at | timestamptz | NOT NULL | |
| deleted_at | timestamptz | | 软删除 |

### part_revisions
零件版本 A/B/C… 状态机：WIP→RELEASED→OBSOLETE。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | uuid | PK | |
| part_master_id | uuid | FK→part_masters CASCADE, NOT NULL | |
| version | varchar(10) | NOT NULL, UNIQUE(master+ver) | |
| status | varchar(20) | NOT NULL, CHECK(WIP/RELEASED/OBSOLETE) | |
| description | text | | |
| checkout_user_id | uuid | FK→users, nullable | **签出锁**（非空=被该用户锁定） |
| checkout_date | timestamptz | | |
| released_by_id | uuid | FK→users | 发布人 |
| released_at | timestamptz | | |
| obsoleted_by_id | uuid | FK→users | 废弃人 |
| obsoleted_at | timestamptz | | |
| created_at | timestamptz | NOT NULL | |
| updated_at | timestamptz | NOT NULL | |
| deleted_at | timestamptz | | 软删除 |

### part_iterations
零件迭代 1/2/3… 签入后 check_in_date 非空即冻结。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | uuid | PK | |
| part_revision_id | uuid | FK→part_revisions CASCADE, NOT NULL | |
| iteration | integer | NOT NULL, CHECK(>0) | 迭代号 |
| iteration_note | text | | 迭代备注 |
| native_cad_file_id | uuid | FK→binary_resources SET NULL | 原生CAD文件 |
| check_in_date | timestamptz | | **非空=已冻结** |
| author_id | uuid | FK→users, NOT NULL | |
| created_at | timestamptz | NOT NULL | |
| updated_at | timestamptz | NOT NULL | |

---

## 三、装配关系（2 表）

### part_usage_links
BOM 行：父迭代使用了哪个子零件。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | uuid | PK | |
| parent_iteration_id | uuid | FK→part_iterations CASCADE, NOT NULL | 父迭代 |
| component_master_id | uuid | FK→part_masters RESTRICT, NOT NULL | 子零件 |
| amount | double | NOT NULL, DEFAULT 1.0 | 用量 |
| unit | varchar(20) | | 单位 |
| optional | boolean | NOT NULL, DEFAULT false | 是否可选 |
| order | integer | NOT NULL, DEFAULT 0 | 排序 |
| comment | text | | 备注 |

### cad_instances
子件在父装配中的空间位置，支持多实例阵列。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | uuid | PK | |
| usage_link_id | uuid | FK→part_usage_links CASCADE, NOT NULL | |
| tx/ty/tz | double | NOT NULL, DEFAULT 0 | 平移量（毫米） |
| rotation_type | varchar(10) | NOT NULL, CHECK(ANGLE/MATRIX) | 旋转模式 |
| rx/ry/rz | double | | ANGLE模式：欧拉角（弧度） |
| m00~m22 | double | | MATRIX模式：3×3旋转矩阵（列优先） |
| order | integer | NOT NULL, DEFAULT 0 | 实例排序 |

---

## 四、文件与转换（3 表）

### binary_resources
文件元数据，实际文件在 vault 磁盘。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | uuid | PK | |
| full_name | varchar(500) | UNIQUE, NOT NULL | vault 路径键 |
| content_length | bigint | NOT NULL, DEFAULT 0 | 文件大小 |
| last_modified | timestamptz | NOT NULL | |

### geometries
迭代的 LOD 几何体 + 包围盒（毫米）。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | uuid | PK | |
| iteration_id | uuid | FK→part_iterations CASCADE, NOT NULL | |
| binary_resource_id | uuid | FK→binary_resources, NOT NULL | GLB 文件 |
| quality | integer | NOT NULL, DEFAULT 0 | LOD级别（0=最高） |
| x_min~z_max | double | NOT NULL | 包围盒 |

### conversions
CAD 转换任务状态。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | uuid | PK | |
| iteration_id | uuid | FK→part_iterations CASCADE, NOT NULL | |
| pending | boolean | NOT NULL, DEFAULT true | 转换中 |
| succeed | boolean | | None=未完成, True/False |
| start_date | timestamptz | NOT NULL | |
| end_date | timestamptz | | |

---

## 五、图文档模块（3 表）

### documents
图文档主数据。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | uuid | PK | |
| code | varchar(64) | NOT NULL | 文档编号 |
| name | varchar(255) | NOT NULL | 文档名称 |
| version | varchar(10) | NOT NULL, DEFAULT A | 版本 |
| status | varchar(32) | NOT NULL, DEFAULT draft | draft/frozen/released/obsolete |
| remark | text | | 备注 |
| file_name | varchar(500) | | 主附件文件名 |
| file_id | uuid | FK→document_attachments SET NULL | 主附件 |
| creator_id | uuid | FK→users, NOT NULL | |
| created_at | timestamptz | NOT NULL | |
| updated_at | timestamptz | NOT NULL | |
| deleted_at | timestamptz | | 软删除 |

### document_attachments
文档附件。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | uuid | PK | |
| document_id | uuid | FK→documents CASCADE, NOT NULL | |
| file_name | varchar(500) | NOT NULL | |
| file_size | bigint | NOT NULL | |
| file_path | varchar(1000) | NOT NULL | |
| file_hash | varchar(64) | | |
| created_at | timestamptz | NOT NULL | |
| updated_at | timestamptz | NOT NULL | |

### document_links
文档↔实体关联（替代旧 JSONB document_links 字段）。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | uuid | PK | |
| document_id | uuid | FK→documents CASCADE, NOT NULL | |
| entity_type | varchar(32) | NOT NULL | part/configuration_item/eco |
| entity_id | uuid | NOT NULL | |
| created_at | timestamptz | NOT NULL | |

### document_group_links
文档可见用户组。

| 字段 | 类型 | 约束 |
|------|------|------|
| document_id | uuid | FK→documents CASCADE, PK |
| group_id | uuid | FK→user_groups CASCADE, PK |

---

## 六、变更管理 ECR（4 表）

### ecrs
工程变更请求。状态机：draft→submitted→reviewing→approved/rejected→closed。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | uuid | PK | |
| ecr_number | varchar(32) | UNIQUE, NOT NULL | ECR编号 |
| title | varchar(255) | NOT NULL | |
| description | text | | |
| reason | varchar(64) | NOT NULL | 变更原因 |
| priority | varchar(16) | NOT NULL | high/urgent/normal/low |
| category | varchar(32) | | |
| status | varchar(16) | NOT NULL | draft/submitted/reviewing/approved/rejected/closed |
| reviewers | jsonb | NOT NULL | 审批人列表 |
| review_mode | varchar(8) | NOT NULL | all/any |
| creator_id | uuid | FK→users, NOT NULL | |
| document_links | jsonb | NOT NULL | |
| cc_users | jsonb | NOT NULL | 抄送人 |
| eco_id | uuid | | 关联的 ECO |
| created_at | timestamptz | | |
| updated_at | timestamptz | | |
| reviewed_at | timestamptz | | |
| closed_at | timestamptz | | |
| deleted_at | timestamptz | | 软删除 |

### ecr_affected_items
ECR 影响的条目。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | uuid | PK | |
| ecr_id | uuid | FK→ecrs CASCADE, NOT NULL | |
| entity_type | varchar(16) | NOT NULL | part/document |
| entity_id | uuid | NOT NULL | |
| entity_code/name/version | varchar | | 冗余快照 |
| change_description | text | | |
| change_type | varchar(32) | | |
| bom_impact | jsonb | NOT NULL | BOM影响分析 |
| created_at | timestamptz | | |

### ecr_review_records
ECR 审批记录。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | uuid | PK | |
| ecr_id | uuid | FK→ecrs CASCADE, NOT NULL | |
| reviewer_id | uuid | FK→users, NOT NULL | |
| reviewer_name | varchar(64) | | |
| decision | varchar(16) | NOT NULL | approved/rejected/returned |
| comment | text | | |
| created_at | timestamptz | | |

### ecr_status_logs
ECR 状态变更日志。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | uuid | PK | |
| ecr_id | uuid | FK→ecrs CASCADE, NOT NULL | |
| from_status | varchar(16) | | |
| to_status | varchar(16) | NOT NULL | |
| operator_id | uuid | FK→users, NOT NULL | |
| operator_name | varchar(64) | | |
| comment | text | | |
| created_at | timestamptz | | |

---

## 七、变更执行 ECO（4 表）

### ecos
工程变更执行单。状态机：draft→submitted→approved→executing→executed→closed。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | uuid | PK | |
| eco_number | varchar(32) | UNIQUE, NOT NULL | ECO编号 |
| ecr_id | uuid | FK→ecrs | 来源ECR |
| title | varchar(255) | NOT NULL | |
| description | text | | |
| reason | varchar(64) | | |
| priority | varchar(16) | NOT NULL | |
| category | varchar(32) | | |
| status | varchar(16) | NOT NULL | |
| reviewers | jsonb | NOT NULL | |
| review_mode | varchar(8) | NOT NULL | |
| creator_id | uuid | FK→users, NOT NULL | |
| document_links | jsonb | NOT NULL | |
| cc_users | jsonb | NOT NULL | |
| release_items | jsonb | NOT NULL | 发布清单 |
| frozen_entities | jsonb | NOT NULL | 冻结快照 |
| created_at | timestamptz | | |
| updated_at | timestamptz | | |
| reviewed_at | timestamptz | | |
| executed_at | timestamptz | | |
| closed_at | timestamptz | | |
| deleted_at | timestamptz | | 软删除 |

### eco_execution_items
ECO 执行明细。5 种动作：upgrade/release/freeze/revert/publish。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | uuid | PK | |
| eco_id | uuid | FK→ecos CASCADE, NOT NULL | |
| source | varchar(8) | NOT NULL | ecr/manual |
| affected_item_id | uuid | FK→ecr_affected_items | |
| entity_type | varchar(16) | NOT NULL | part/document |
| entity_id | uuid | | 目标实体 |
| entity_code/name/version | varchar | | 冗余快照 |
| action | varchar(16) | NOT NULL | upgrade/release/freeze/revert |
| status | varchar(16) | NOT NULL | pending/done/failed |
| detail | jsonb | NOT NULL | |
| new_entity_id | uuid | | 升级后的新实体ID |
| new_version | varchar(32) | | 新版本号 |
| sort_order | integer | NOT NULL | |
| executed_at | timestamptz | | |

### eco_review_records / eco_status_logs
结构与 ECR 的 review_records / status_logs 相同，FK 指向 ecos。

---

## 八、构型管理（8 表）

### configuration_items
构型项（产品定义/BOM 顶层）。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | uuid | PK | |
| code | varchar(64) | NOT NULL | 构型编号 |
| name | varchar(255) | NOT NULL | |
| spec | varchar(255) | | 规格 |
| remark | text | | |
| document_links | jsonb | | |
| creator_id | uuid | FK→users | |
| created_at | timestamptz | | |
| updated_at | timestamptz | | |
| deleted_at | timestamptz | | 软删除 |

### configuration_item_parts
构型项→零件关联。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | uuid | PK | |
| configuration_item_id | uuid | FK CASCADE, NOT NULL | |
| part_type | varchar(16) | NOT NULL | part/assembly |
| part_id | uuid | NOT NULL | →part_masters |
| is_required | boolean | NOT NULL | |
| quantity | integer | NOT NULL | |
| sort_order | integer | NOT NULL | |

### configuration_item_children
构型项层级关系。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | uuid | PK | |
| parent_id | uuid | FK CASCADE, NOT NULL | |
| child_id | uuid | FK CASCADE, NOT NULL | |
| is_required | boolean | NOT NULL | |
| quantity | integer | NOT NULL | |
| sort_order | integer | NOT NULL | |

### configuration_profiles
配置方案。状态机：draft→submitted→approved→archived。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | uuid | PK | |
| code | varchar(64) | NOT NULL | 方案编号 |
| name | varchar(255) | NOT NULL | |
| configuration_item_id | uuid | FK | 根构型项 |
| status | varchar(16) | NOT NULL | |
| effectivity_start/end | varchar(32) | | 有效起止 |
| reviewers | jsonb | NOT NULL | |
| review_mode | varchar(8) | NOT NULL | |
| creator_id | uuid | FK→users, NOT NULL | |
| submitted_at/reviewed_at/archived_at | timestamptz | | |

### configuration_profile_items / configuration_working_items
方案清单项和工作副本。working_items 用于编辑回写。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | uuid | PK | |
| profile_id | uuid | FK CASCADE, NOT NULL | |
| source_config_item_id | uuid | FK | |
| item_type | varchar(16) | NOT NULL | |
| item_id | uuid | NOT NULL | |
| is_required/seleted | boolean | NOT NULL | |
| quantity | integer | NOT NULL | |
| source_type | varchar(16) | NOT NULL | |
| sort_order | integer | NOT NULL | |

### configuration_review_records / configuration_status_logs
方案审批和状态日志，结构与 ECR 的同名表一致。

---

## 九、库存管理（8 表）

### warehouses
仓库。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | uuid | PK | |
| code | varchar(64) | NOT NULL | |
| name | varchar(255) | NOT NULL | |
| type | varchar(32) | | |
| default_keeper_id | uuid | FK→users | 默认保管人 |
| status | varchar(32) | NOT NULL | |
| remark | text | | |
| created_at/updated_at | timestamptz | | |
| deleted_at | timestamptz | | 软删除 |

### inventory_materials
物料主数据。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | uuid | PK | |
| code | varchar(64) | NOT NULL | 物料编号 |
| name | varchar(255) | NOT NULL | |
| spec | varchar(255) | | 规格 |
| unit | varchar(32) | | 单位 |
| source_type | varchar(16) | NOT NULL | standalone/part/assembly |
| ref_entity_type | varchar(16) | | 来源实体类型 |
| ref_entity_id | uuid | | 来源实体ID（→PartMaster） |
| track_mode | varchar(16) | NOT NULL | quantity/batch |
| safety_stock | numeric | | 安全库存 |
| status | varchar(32) | NOT NULL | |
| created_at/updated_at | timestamptz | | |
| deleted_at | timestamptz | | 软删除 |

### inventory_stock
库存余额。mat+wh+batch 联合唯一。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | uuid | PK | |
| material_id | uuid | FK, NOT NULL | |
| warehouse_id | uuid | FK, NOT NULL | |
| batch_no | varchar(64) | NOT NULL | 批次号 |
| quantity | numeric | NOT NULL | |
| updated_at | timestamptz | | |

### inventory_ledger
库存流水账。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | uuid | PK | |
| material_id | uuid | NOT NULL | |
| warehouse_id | uuid | NOT NULL | |
| batch_no | varchar(64) | NOT NULL | |
| direction | varchar(4) | NOT NULL | in/out |
| quantity | numeric | NOT NULL | |
| balance_after | numeric | NOT NULL | 变动后余额 |
| doc_id/doc_type/doc_number/doc_line_id | | | 来源单据追踪 |
| operator_id/name | | | |
| created_at | timestamptz | | |

### inventory_documents
库存单据。状态机含提交/撤回/审批/过账。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | uuid | PK | |
| doc_number | varchar(32) | UNIQUE, NOT NULL | 单号 |
| doc_type | varchar(16) | NOT NULL | inbound/outbound/transfer/stocktake/adjustment |
| biz_type | varchar(32) | | 业务类型 |
| status | varchar(16) | NOT NULL | |
| warehouse_id | uuid | FK | 仓库 |
| to_warehouse_id | uuid | FK | 调拨目标仓 |
| reviewers | jsonb | NOT NULL | |
| keeper_id | uuid | FK→users | 保管人 |
| creator_id | uuid | FK→users, NOT NULL | |
| reviewed_at/posted_at | timestamptz | | |
| created_at/updated_at | timestamptz | | |
| deleted_at | timestamptz | | 软删除 |

### inventory_document_lines
单据行项目。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | uuid | PK | |
| doc_id | uuid | FK CASCADE, NOT NULL | |
| material_id | uuid | FK, NOT NULL | |
| batch_no | varchar(64) | NOT NULL | |
| quantity | numeric | NOT NULL | |
| direction | varchar(4) | | 仅 adjustment 使用 |
| book_quantity | numeric | | 账面数量（盘点用） |
| counted_quantity | numeric | | 实盘数量（盘点用） |
| sort_order | integer | NOT NULL | |

### inventory_review_records / inventory_status_logs
单据审批记录和状态日志，结构同 ECR 同名表。

---

## 十、项目管理（6 表）

### projects
项目主数据。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | uuid | PK | |
| code | varchar(64) | NOT NULL | 项目编号 |
| name | varchar(255) | NOT NULL | |
| owner_id | uuid | FK→users, NOT NULL | 负责人 |
| status | varchar(16) | NOT NULL | 进行中/已完成/已暂停/已归档 |
| planned_start/end | varchar(32) | | |
| description | text | | |
| created_at/updated_at | timestamptz | | |
| deleted_at | timestamptz | | 软删除 |

### project_members
项目成员。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | uuid | PK | |
| project_id | uuid | FK CASCADE, NOT NULL | |
| user_id | uuid | FK→users, NOT NULL | |
| role_in_project | varchar(8) | NOT NULL | 经理/成员 |
| created_at | timestamptz | | |

### project_tasks
项目任务，支持树形结构（parent_id 自引用）。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | uuid | PK | |
| project_id | uuid | FK CASCADE, NOT NULL | |
| parent_id | uuid | FK→project_tasks, nullable | 父任务 |
| code | varchar(64) | NOT NULL | 任务编号 |
| name | varchar(255) | NOT NULL | |
| task_type | varchar(8) | NOT NULL | 任务/里程碑/评审 |
| assignee_id | uuid | FK→users | 负责人 |
| status | varchar(8) | NOT NULL | 未开始/进行中/已完成/挂起 |
| priority | varchar(4) | NOT NULL | 高/中/低 |
| planned_start/end | date | | 甘特图日期 |
| actual_start/end | date | | 实际日期 |
| sort_order | integer | NOT NULL | |
| description | text | | |
| created_at/updated_at | timestamptz | | |
| deleted_at | timestamptz | | 软删除 |

### project_task_links
任务关联实体。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | uuid | PK | |
| task_id | uuid | FK CASCADE, NOT NULL | |
| entity_type | varchar(16) | NOT NULL | part/document/ec/configuration_item |
| entity_id | uuid | NOT NULL | |
| created_at | timestamptz | | |

### project_task_comments
任务评论。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | uuid | PK | |
| task_id | uuid | FK CASCADE, NOT NULL | |
| user_id | uuid | FK→users, NOT NULL | |
| content | text | NOT NULL | |
| created_at/updated_at | timestamptz | | |
| deleted_at | timestamptz | | 软删除 |

### project_task_deps
任务依赖关系。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | uuid | PK | |
| project_id | uuid | FK CASCADE, NOT NULL | |
| predecessor_id | uuid | FK→project_tasks, NOT NULL | 前置任务 |
| successor_id | uuid | FK→project_tasks, NOT NULL | 后置任务 |
| dep_type | varchar(2) | NOT NULL | FS/SS/FF/SF |
| lag_days | integer | NOT NULL | 滞后天数 |
| created_at | timestamptz | | |

---

## 十一、支撑模块（4 表）

### operation_logs
操作审计日志。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | uuid | PK | |
| user_id | uuid | FK→users | |
| username | varchar(64) | | |
| action | varchar(64) | NOT NULL | 操作动作 |
| target_type | varchar(32) | | 目标实体类型 |
| target_id | varchar(64) | | 目标实体ID |
| detail | text | | 操作详情 |
| ip_address | varchar(64) | | |
| created_at | timestamptz | | |

### component_attachments
零件附件（兼容旧 myPDM components 表）。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | uuid | PK | |
| component_id | uuid | FK→components, NOT NULL | |
| category | varchar(32) | NOT NULL | cad/production |
| file_name | varchar(255) | | |
| file_size | integer | | |
| file_path | varchar(512) | | |
| file_hash | varchar(64) | | |
| created_at | timestamptz | | |

### components
旧 myPDM 零件表（兼容保留）。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| id | uuid | PK | |
| code | varchar(64) | NOT NULL | 编号 |
| name | varchar(255) | NOT NULL | |
| spec | varchar(255) | | 规格 |
| version | varchar(32) | | |
| status | varchar(32) | NOT NULL | |
| remark | text | | |
| revisions | jsonb | | 版本历史 |
| revision_parent_id | uuid | FK→components | |
| creator_id | uuid | FK→users | |
| document_links | jsonb | | |
| created_at/updated_at | timestamptz | NOT NULL | |
| deleted_at | timestamptz | | 软删除 |

---

## 十二、ER 关系总览

```
workspaces ──┬── users ───── user_group_members ──── user_groups
             │
             ├── part_masters ── document_links ── documents ── document_attachments
             │       │                                    └── document_group_links → user_groups
             │       ├── component_attachments
             │       ├── part_revisions
             │       │       ├── part_iterations
             │       │       │       ├── part_usage_links ──── cad_instances
             │       │       │       ├── geometries ── binary_resources
             │       │       │       └── conversions
             │       │       └── checkout_user_id → users
             │       └── (ecr/eco/configuration/inventory refs via entity_id UUID)
             │
             ├── configuration_items ── configuration_item_parts → part_masters
             │       └── configuration_item_children (自引用)
             │       └── configuration_profiles ── profile_items / working_items / review / log
             │
             ├── ecrs ── ecr_affected_items / ecr_review_records / ecr_status_logs
             │    └── ecos ── eco_execution_items / eco_review_records / eco_status_logs
             │
             ├── warehouses ── inventory_materials ── inventory_stock / inventory_ledger
             │              └── inventory_documents ── document_lines / review / log
             │
             ├── projects ── project_members / project_tasks
             │                    ├── project_task_links
             │                    ├── project_task_comments
             │                    └── project_task_deps (predecessor/successor)
             │
             └── operation_logs
```
