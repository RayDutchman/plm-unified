# 容器架构说明

> plm-unified 的 Docker 服务编排说明。共 7 个服务，通过 `docker/docker-compose.yml` 定义。  
> 入口：根目录 `docker-compose.yml`（使用 `include` 引用）。

---

## 一、整体架构图

```
用户浏览器 / CATIA sync.py
        │
        ▼
┌─────────────────────────────────────────────────────────────┐
│  宿主机暴露端口                                              │
│                                                             │
│  :8000  ──── backend   (FastAPI 后端 API)                   │
│  :5432  ──── db        (PostgreSQL 16，开发调试用)          │
│  :6379  ──── redis     (Redis 7，开发调试用)                │
│  :9092  ──── kafka     (Kafka，开发调试用)                  │
│  :9200  ──── es        (Elasticsearch，开发调试用)          │
└─────────────────────────────────────────────────────────────┘
        │
        ▼ Docker 内部网络（容器名互访）
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  backend:8000                                               │
│    ├── → db:5432            (PostgreSQL，数据持久化)        │
│    ├── → redis:6379         (缓存/会话)                     │
│    ├── → kafka:9092         (发送 CONVERT 转换消息)         │
│    └── → es:9200            (全文搜索，M2 后启用)           │
│                                                             │
│  conversion:8080                                            │
│    ├── ← kafka:9092         (消费 CONVERT 消息)             │
│    └── → backend:8000       (HTTP 回调，写入转换结果)       │
│                                                             │
│  kafka ← zookeeper:2181     (Kafka 依赖)                    │
└─────────────────────────────────────────────────────────────┘
```

---

## 二、服务清单

| 服务名 | 镜像 | 端口 | 说明 |
|--------|------|------|------|
| `db` | `postgres:16` | 5432 | PostgreSQL 数据库，数据持久化到 `db_data` volume |
| `redis` | `redis:7-alpine` | 6379 | 缓存、分布式锁（签出保护）、会话 |
| `zookeeper` | `confluentinc/cp-zookeeper:7.5.0` | 2181 | Kafka 依赖，仅内部访问 |
| `kafka` | `confluentinc/cp-kafka:7.5.0` | 9092 | 消息队列，主 topic：`CONVERT` |
| `es` | `elasticsearch:8.11.0` | 9200 | 全文搜索（M2 后启用） |
| `backend` | 本地构建（`backend/Dockerfile`） | 8000 | FastAPI 后端，挂载 `vault_data` |
| `conversion` | 本地构建（`conversion/Dockerfile.jvm`） | 8080 | CAD 转换服务（Quarkus），挂载 `vault_data` |

---

## 三、数据流

### 3.1 零件数据写入

```
sync.py（CATIA Copilot）
  │
  ▼ PUT /api/workspaces/{ws}/parts/{num}/versions/{ver}/iterations/{iter}
  │   body: { components: [...], cadInstances: [...] }
  │
  ▼ FastAPI backend
  │   → 写 part_masters / part_revisions / part_iterations / part_usage_links / cad_instances
  │   → 持久化到 PostgreSQL
```

### 3.2 CAD 文件上传与转换

```
sync.py（CATIA Copilot）
  │
  ▼ PUT /api/files/{ws}/parts/{num}/{ver}/{iter}/nativecad
  │
  ▼ FastAPI backend
  │   → 保存文件到 vault（Docker volume: vault_data）
  │   → 写 binary_resources 记录
  │   → 发送 Kafka 消息到 topic CONVERT
  │         消息 key: {ws}/{num}/{ver}-{iter}
  │         消息 body: { partIterationKey, binaryResource, userToken }
  │
  ▼ conversion 服务（消费 CONVERT）
  │   → 从 vault 读取 .stp 文件
  │   → convert_step_glb.py（cadquery-ocp → GLB）
  │   → 写 GLB 到 vault
  │   → HTTP 回调 backend: POST /api/conversions/callback
  │
  ▼ FastAPI backend（处理回调）
      → 写 geometries 记录（含包围盒）
      → 更新 part_iterations.conversion_succeed
```

### 3.3 3D 预览查询

```
前端（React + Three.js）
  │
  ▼ GET /api/workspaces/{ws}/products/{ci}/instances?configSpec=latest
  │
  ▼ FastAPI backend
  │   → 递归遍历装配树（part_usage_links + cad_instances）
  │   → 累乘变换矩阵，输出每个叶子零件的全局 4×4 矩阵
  │
  ▼ 前端 Three.js
      → mesh.applyMatrix4(matrix)
      → fetch GLB 文件（从 vault 经 backend 代理）
```

---

## 四、Volume 说明

| Volume | 挂载到 | 说明 |
|--------|--------|------|
| `db_data` | db:/var/lib/postgresql/data | PostgreSQL 数据持久化 |
| `es_data` | es:/usr/share/elasticsearch/data | Elasticsearch 索引持久化 |
| `vault_data` | backend:/vault，conversion:/vault | 文件存储共享卷（CAD 原文件 + GLB 转换结果） |

**关键设计：** `backend` 和 `conversion` 共享同一个 `vault_data`，backend 写入 CAD 文件，conversion 读取并写入 GLB 结果。

---

## 五、Backend 环境变量

```yaml
DATABASE_URL: postgresql://plm:plmpass@db:5432/plm_unified
REDIS_URL: redis://redis:6379
KAFKA_BOOTSTRAP_SERVERS: kafka:9092
JWT_SECRET: change-this-in-production   # 生产环境必须更换
VAULT_PATH: /vault
```

---

## 六、与旧架构对比（CATIA-Copilot-PLM）

| 维度 | plm-unified（新） | CATIA-Copilot-PLM（旧） |
|------|-------------------|------------------------|
| 后端 | FastAPI（Python） | Payara/Java EE |
| 前端 | myPDM React SPA | Backbone.js + AMD |
| 数据库 | PostgreSQL 16（自管） | PostgreSQL 13（DocDoku） |
| 服务数量 | 7 个 | 11 个 |
| Kafka 镜像 | confluentinc/cp-kafka:7.5.0 | confluentinc/cp-kafka:7.5.0（旧版为 wurstmeister） |
| 代理层 | 暂无（开发阶段直连 8000） | Nginx + SSL proxy |
| 认证 | JWT（python-jose） | JWT（Java EE） |

---

*最后更新：2026-06-26*
