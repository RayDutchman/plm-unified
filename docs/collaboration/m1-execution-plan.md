# M1 执行方案（详细分解）

> 本文档是 [`milestones.md`](./milestones.md) 中 **M1：新 Schema + 认证 + 基础零件 API** 的落地执行细则。
> - **里程碑追踪（状态回填）** 以 `milestones.md` 的 M1 表为准，本文档不重复维护状态。
> - 本文档负责：修订依赖图、阶段编排、B 任务详细方案、A 任务接口契约、协作检查点。
> - 角色：**A** = 熟悉 DocDoku/CATIA（同事）；**B** = 熟悉 myPDM/FastAPI（本人）。

---

## 一、M1 目标与验收条件

**目标**：在 plm-unified 后端落地 DocDoku 三层零件模型（Master/Revision/Iteration）、JWT 认证、基础零件 CRUD 与签入签出状态机。

**✅ 达成条件（逐项可勾选）**：

- [ ] 能通过 API 创建零件（PartMaster + 首个 Revision A + 首个 Iteration 1）
- [ ] 能签出（checkout）、修改、签入（checkin），签入产生新 Iteration
- [ ] 第二个用户对已签出的 Revision 再次签出 → 返回 **409 Conflict**
- [ ] 能撤销签出（undo checkout）
- [ ] 数据正确写入新库 `plm_unified`
- [ ] JWT 登录、token 校验、refresh 全链路可用
- [ ] M1 验收测试脚本（pytest）全绿

---

## 二、现状基线（M0 产物盘点）

| 项 | 状态 | 说明 |
|---|---|---|
| FastAPI 脚手架 | ✅ | `backend/app/` 下 `core/ crud/ models/ schemas/ routers/` 均为空 `__init__.py`；`main.py` 仅含 `/health` |
| 依赖清单 | ✅ | `requirements.txt` 已含 `sqlalchemy==2.0.36`、`alembic==1.14.0`、`psycopg2-binary`、`python-jose`、`passlib[bcrypt]`、`numpy` |
| DDL 设计 | ✅（文档） | `docs/architecture/data-model.md`（标注 M1.1）已是完整 DDL 设计 —— **任务 1.1 实质已完成** |
| Docker 编排 | ✅ | `docker/docker-compose.yml`：db=postgres:15（库 `plm_unified`/用户 `plm`），宿主端口 5435/6380/9093/8010 |
| 后端环境变量 | ✅ | compose 注入 `DATABASE_URL`、`JWT_SECRET`、`VAULT_PATH=/vault`、`KAFKA_BOOTSTRAP_SERVERS` |

**待落地缺口（M1 要补的）**：

1. ❌ 无 `database.py`（引擎、Session、Base、`get_db`）
2. ❌ 无任何 SQLAlchemy ORM 模型
3. ❌ 无 Alembic（无 `alembic.ini`、无 `migrations/`，`data-model.md` 引用的 `backend/sql/init.sql` 也不存在）
4. ❌ 无认证、无 CRUD、无路由

---

## 三、修订后的依赖图与分工

### 计划缺口修正：ORM 模型归属

原 `milestones.md` 的 M1 表未指定**谁写 SQLAlchemy ORM 模型**，但 1.4（Alembic）与 1.6（CRUD）都依赖它。**已决策：B 写全部核心 ORM 模型，Alembic 用 `--autogenerate` 从模型生成迁移。** 这把 B 的工作前移到关键路径起点 —— **A 的 CRUD/签入签出（1.6/1.7）要等 B 的模型冻结后才能动**。

### 执行模型：地基先行（Foundation-First）

```
Phase 0 ── 数据地基（B 独占冲刺，最短关键路径）
   B: config + database.py(Base/Session/get_db) + 全部核心 ORM 模型 + Alembic 初版迁移
   ↓ 【模型冻结 Gate】← A 业务语义 review(1.3) 在此通过
Phase 1 ── 并行建造（模型已冻结，A/B 互不阻塞）
   B: JWT 认证模块(1.5)        ‖   A: PartMaster/Revision CRUD(1.6) → 签入签出(1.7)
   ↓
Phase 2 ── 集成验收
   B: review 签入签出 + 补 Pydantic schema + API 文档(1.8)
   AB: M1 验收测试脚本(1.9)
```

### 依赖图

```
1.2 B工程review ─┐
                 ├─→ 1.4 B:ORM模型+Alembic迁移 ──【模型冻结】─┬─→ 1.5 B:JWT认证
1.3 A业务review ─┘   (= Phase 0)                              │
                                                              └─→ 1.6 A:CRUD ─→ 1.7 A:签入签出
                                                                                    │
                                              1.8 B:review+schema+文档 ←───────────┘
                                                          │
                                              1.9 AB:验收测试 ←─ 1.7 完成
```

### 分工速查

| # | 行动项 | 负责 | 阶段 | 前置 |
|---|---|---|---|---|
| 1.2 | review DDL 工程规范（UUID/软删除/updated_at/索引） | B | P0 | data-model.md |
| 1.3 | review DDL 业务语义（对照 DocDoku） | A | P0 | data-model.md |
| 1.4 | 全部核心 ORM 模型 + Alembic 首版迁移 | **B** | P0 | 1.2 & 1.3 |
| 1.5 | JWT 认证模块（移植 myPDM） | B | P1 | 1.4（users 表） |
| 1.6 | PartMaster/PartRevision CRUD | **A** | P1 | 1.4（模型冻结） |
| 1.7 | 签入/签出/撤销签出状态机 | **A** | P1 | 1.6 |
| 1.8 | review 签入签出 + Pydantic schema + API 文档 | B | P2 | 1.7 |
| 1.9 | M1 验收测试脚本 | AB | P2 | 1.7 |

---

## 四、Phase 0：数据地基（B 详细方案）

### 4.1 任务 1.2 — DDL 工程规范 review

**做什么**：以工程视角审 `data-model.md`，产出 review 结论（直接在 PR 描述或 `docs/decisions/` 追加一条），重点核查清单：

- [ ] 所有表 UUID 主键 `default=uuid.uuid4`（Postgres 侧 `gen_random_uuid()` 或应用侧生成，二选一并统一）
- [ ] 软删除字段 `deleted_at` 覆盖：`part_masters`、`part_revisions`、`users`、`workspaces`（按 data-model.md §一）
- [ ] `updated_at` 触发器（或 SQLAlchemy `onupdate=func.now()`）在所有可变表挂载
- [ ] 外键 `ON DELETE` 策略明确（CASCADE / RESTRICT），无孤儿
- [ ] 唯一约束：`part_masters(workspace_id, number)`、`part_revisions(part_master_id, version)`、`part_iterations(part_revision_id, iteration)`、`binary_resources(full_name)`
- [ ] 索引覆盖 data-model.md §五列出的 11 条
- [ ] CHECK 约束：`part_iterations.iteration > 0`、`cad_instances` 的 ANGLE/MATRIX 互斥非空

**关键决策点（需与 A 对齐后写进模型）**：
1. **UUID 生成位置**：推荐**应用侧** `default=uuid.uuid4`（与 myPDM `User` 一致，迁移可移植，不依赖 `uuid-ossp`/`pgcrypto` 扩展）。
2. **枚举类型**：`part_revisions.status`、`cad_instances.rotation_type` 用 PG 原生 ENUM 还是 `VARCHAR + CHECK`？推荐 **VARCHAR + CHECK**（Alembic 对原生 ENUM 的变更支持差，后续加状态值更省事）。

### 4.2 任务 1.4 — ORM 模型 + Alembic 首版迁移（核心交付）

**首批建表范围**：一次性建齐 data-model.md 的 9 张表 —— `workspaces`、`users`、`part_masters`、`part_revisions`、`part_iterations`、`binary_resources`、`geometries`、`part_usage_links`、`cad_instances`。
> 理由：DDL 已全部设计完，一次建齐避免 M2 再补迁移产生 churn。`geometries/part_usage_links/cad_instances` 在 M1 不被业务调用，但建表无害。

**产出文件清单**：

```
backend/app/core/config.py          # pydantic-settings：读 DATABASE_URL/JWT_SECRET/VAULT_PATH 等
backend/app/database.py             # engine, SessionLocal, Base, get_db()
backend/app/models/__init__.py      # 汇总 import 全部模型（Alembic autogenerate 必须能发现）
backend/app/models/workspace.py
backend/app/models/user.py
backend/app/models/part.py          # PartMaster / PartRevision / PartIteration
backend/app/models/binary.py        # BinaryResource / Geometry
backend/app/models/assembly.py      # PartUsageLink / CADInstance
backend/alembic.ini
backend/migrations/env.py           # target_metadata = Base.metadata；从 DATABASE_URL 读连接
backend/migrations/versions/0001_initial_schema.py
```

**实现要点**：
- `database.py` 读 **`DATABASE_URL`**（compose 已注入 `postgresql://plm:plmpass@db:5432/plm_unified`），不沿用 myPDM 的拆分 `POSTGRES_*` 变量。
- `migrations/env.py` 的 `target_metadata` 指向 `Base.metadata`；务必在 env.py 顶部 `from app import models` 触发全部模型注册，否则 autogenerate 漏表。
- 模型层禁止 import 任何 CRUD/路由，保持纯数据层（A 的 CRUD 单向依赖模型）。
- 中文注释标注每个模型对应的 DocDoku 实体（如 `# 对应 DocDoku PartRevision`）。

**验收**：`alembic upgrade head` 在干净的 `plm_unified` 库执行成功，9 张表 + 索引 + 约束齐备；`alembic downgrade base` 可回滚。

### 4.3 模型冻结 Gate

1.4 合并前必须收到 A 的 1.3 业务语义 review approve。合并即"模型冻结"，A 据此动 1.6/1.7。冻结后若需改模型，走 `fix/` 分支并通知 A。

---

## 五、Phase 1：B 任务 — JWT 认证模块（1.5）

**做什么**：移植 myPDM `backend/app/routers/auth.py` 到 plm-unified，适配新 `users` 表。

**直接可复用（myPDM 已验证）**：
- `create_access_token` / `create_refresh_token` / `get_current_user` / `get_current_active_user` / `require_role`
- 端点：`POST /auth/token`、`POST /auth/refresh`、`GET /auth/me`、`POST /auth/change-password`
- token 形态：`{access_token, refresh_token, token_type:"bearer"}`，payload 含 `sub`(username)、`role`、`typ`、`exp`

**产出文件**：
```
backend/app/core/security.py        # 密码哈希 + token 编解码（从 auth.py 抽出可复用部分）
backend/app/crud/user.py            # authenticate_user / get_user_by_username / get_password_hash / verify_password
backend/app/schemas/auth.py         # Token / RefreshRequest / ChangePasswordRequest / UserResponse
backend/app/schemas/user.py         # UserCreate / UserResponse（含 workspace_id）
backend/app/routers/auth.py
```

**适配差异（务必处理）**：

1. **users 表多了 `workspace_id`**：myPDM `User` 无此字段，新表有 `workspace_id FK→workspaces`。`UserResponse`、`create_user`、登录后 token 可带 `workspace_id`（供后续按工作空间隔离数据）。
2. **密码哈希口径** ⚠️：myPDM 用**裸 `bcrypt`**，但 plm-unified `requirements.txt` 写的是 `passlib[bcrypt]`。两者不能混用且有坑 —— **passlib 1.7.4 + bcrypt ≥4.1 会报 `__about__` 警告/异常**。
   - **推荐**：plm-unified 统一用 **passlib `CryptContext(schemes=["bcrypt"])`**（FastAPI 惯用、requirements 已声明），但在 `requirements.txt` **加 `bcrypt==4.0.1` 锁版本**规避兼容坑。
   - 备选：照搬 myPDM 裸 bcrypt，从 requirements 移除 passlib。二选一，写进 PR 描述。
3. **JWT_SECRET 强度** ⚠️：myPDM auth.py 有 `len(SECRET_KEY) < 32 → RuntimeError`。但 compose 里 `JWT_SECRET: change-this-in-production`（25 字符）**会导致后端启动即崩**。需同步把 compose 的默认值换成 ≥32 字符（`openssl rand -hex 32`），并在 `docs/setup/local-dev-guide.md` 注明。
4. **种子用户**：M1 测试需要至少 1 个用户。在 Alembic 迁移或单独 seed 脚本里插入一个 `admin`（密码哈希用上面选定的方案），供 1.9 测试登录。需要一个默认 `workspace` 行（users.workspace_id 非空时）。

**验收**：`POST /auth/token` 用种子用户拿到 token；带 token 访问受保护端点 200，无 token/错 token 401。

---

## 六、Phase 1：A 任务接口契约（1.6 / 1.7，B 视角约定）

> 这部分是 A 主写，列在此处是为**锁定 B 依赖的接口形状**，便于 1.5 认证与 1.8/1.9 对接。A 的实现权威参考：DocDoku `docdoku-plm-server-ejb` 下的 `PartManagerBean` / `CheckInManager` / `CheckOutManager`（在 CATIA-Copilot-PLM 仓库）。

### 1.6 PartMaster / PartRevision CRUD（建议端点）

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/parts` | 创建 PartMaster + Revision A + Iteration 1 |
| `GET` | `/api/parts` | 列表（按 workspace 过滤、分页） |
| `GET` | `/api/parts/{number}` | 取单个零件（含 revisions/iterations） |

创建零件时自动生成首个 Revision（version="A"，status="WIP"）和首个 Iteration（iteration=1）—— 对应 DocDoku `createPartMaster` 行为。

### 1.7 签入签出状态机（建议端点 + 并发约定）

| 方法 | 路径 | 成功 | 冲突 |
|---|---|---|---|
| `PUT` | `/api/parts/{number}/{version}/checkout` | 200，置 `checkout_user_id`=当前用户 | **409** 若已被他人签出 |
| `PUT` | `/api/parts/{number}/{version}/checkin` | 200，冻结当前 iteration（写 `check_in_date`），生成下一 iteration | 409 若未签出 / 非签出本人 |
| `PUT` | `/api/parts/{number}/{version}/undocheckout` | 200，清 `checkout_user_id`，丢弃未签入的草稿 iteration | 409 若未签出 |

**并发保护**：签出/签入对 `part_revisions` 行用 `SELECT ... FOR UPDATE`（SQLAlchemy `with_for_update()`）。这是 M1 达成条件"第二用户签出返回 409"的核心，也是 M4 ECO 执行复用的同一套机制。**B 在 1.8 重点 review 这里。**

---

## 七、Phase 2：B 任务 — review + schema + 文档（1.8）

**做什么**：
1. **review A 的签入签出实现**，对照清单：
   - [ ] `with_for_update()` 真正生效（同一事务内，非自动提交）
   - [ ] 409 在三种场景正确触发（重复签出 / 非本人签入 / 未签出撤销）
   - [ ] 签入正确生成新 iteration 且旧 iteration 冻结（`check_in_date` 非空后不可改）
   - [ ] checkout/checkin 边界与软删除、status=RELEASED 的交互（RELEASED 版本不可签出）
2. **补 Pydantic schema**：`schemas/part.py`（`PartCreate`、`PartResponse`、`RevisionResponse`、`IterationResponse`、`CheckoutResponse`），统一字段命名 `camelCase`↔`snake_case` 映射策略（FastAPI `alias` / `populate_by_name`）。
3. **补接口文档**：更新 `docs/reference/rest-api.md`，覆盖零件 CRUD + 签入签出 + 认证端点；确认 `/api/docs` (Swagger) 可正常渲染。

**验收**：Swagger 能看到全部 M1 端点及 schema；rest-api.md 与实现一致。

---

## 八、Phase 2：M1 验收测试（1.9，AB 共同）

**形态**：`backend/tests/test_m1_acceptance.py`（pytest + httpx/TestClient + 测试库或事务回滚 fixture）。

**覆盖流程**：
```
登录(种子用户)
 → 创建零件 P-001         （断言 Revision A / Iteration 1 自动生成）
 → checkout A             （断言 checkout_user_id 被置位）
 → 第二用户 checkout A    （断言 409）
 → checkin A              （断言生成 Iteration 2，Iteration 1 冻结）
 → undocheckout（新一轮） （断言草稿被丢弃）
 → 校验数据落库正确
```

**分工**：B 搭测试脚手架（fixture、测试库、登录辅助）；A 补零件/签出断言；共同跑通。

**验收**：`pytest backend/tests/test_m1_acceptance.py` 全绿 → 回填 `milestones.md` M1 全部 ✅ → PR 合 dev → 联调 → PR 合 main（M1 里程碑达成）。

---

## 九、风险与协作检查点

| 风险 | 触发点 | 应对 |
|---|---|---|
| **JWT_SECRET 过短致后端崩** | 1.5 移植 auth.py | compose 默认值换 ≥32 字符；local-dev-guide 注明 |
| **passlib/bcrypt 4.x 兼容坑** | 1.5 密码哈希 | 选定单一方案 + 锁 `bcrypt==4.0.1`，不混用 |
| **autogenerate 漏表** | 1.4 Alembic | env.py 顶部 import 全部模型；生成后人工核对 9 表 |
| **模型冻结后被改，阻断 A** | P0→P1 交界 | 冻结 Gate + `fix/` 分支 + 即时通知 |
| **users.workspace_id 非空但无默认 workspace** | 1.4/1.5 种子 | 迁移内插入默认 workspace 行 |
| **ENUM 用原生类型后难加值** | 1.4 建模 | status/rotation_type 用 VARCHAR + CHECK |

**协作节奏**：
1. B 先开 `feat/m1-data-foundation`（1.2+1.4）→ PR，A review(1.3) approve → 合 dev（**模型冻结**）。
2. 冻结后 B 开 `feat/m1-auth`(1.5)，A 开 `feat/m1-part-crud`(1.6→1.7)，并行。
3. 两条合 dev 后，B 开 `feat/m1-schema-docs`(1.8)，AB 共写 `feat/m1-acceptance-test`(1.9)。
4. 全绿 → 回填 `milestones.md` → PR dev→main。

---

*文档版本：M1-plan v1 | 维护者：B | 状态追踪见 milestones.md*
