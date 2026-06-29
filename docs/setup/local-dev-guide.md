# 本地开发环境搭建

> 面向开发者的本地环境搭建指南。适用于 plm-unified 全栈开发（FastAPI 后端 + React 前端 + 转换服务）。

---

## 一、前提条件

| 工具 | 版本要求 | 说明 |
|------|----------|------|
| Docker | 24+ | 含 Compose V2（`docker compose` 命令） |
| Python | 3.11+ | 后端本地开发（可选，Docker 开发不需要） |
| Node.js | 20+ | 前端开发 |
| Git LFS | 3.0+ | 拉取 `conversion/wheels/*.whl` |

---

## 二、克隆仓库

```bash
# 安装 Git LFS（首次）
git lfs install

# 克隆（自动拉取 LFS 文件）
git clone https://github.com/RayDutchman/plm-unified.git
cd plm-unified
git lfs pull   # 确保 conversion/wheels/*.whl 已下载（约 200MB）
```

---

## 三、一键启动（全栈 Docker）

```bash
# 构建并启动所有服务（首次约 5~10 分钟，需下载镜像 + 构建）
docker compose up -d

# 验证后端健康
curl http://localhost:8000/health
# 期望返回：{"status": "ok", "version": "0.1.0"}

# 查看日志
docker compose logs -f backend
docker compose logs -f conversion
```

服务就绪后：
- FastAPI 文档：http://localhost:8000/api/docs
- 前端（开发模式，见下方）：http://localhost:5173

---

## 四、前端开发模式

前端独立开发，热更新，不依赖 Docker 前端镜像：

```bash
cd frontend
npm install
npm run dev      # 启动 Vite dev server，监听 :5173
```

前端通过代理访问后端（`vite.config.ts` 中配置 `/api` → `http://localhost:8000`）。

---

## 五、后端本地开发模式

```bash
cd backend

# 创建虚拟环境
python3 -m venv .venv
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 启动（需要 Docker 中的 db/redis/kafka 在运行）
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

> 本地后端开发时保持 `docker compose up db redis kafka` 运行即可，不需要完整启动所有服务。

---

## 六、数据库初始化

首次启动时 PostgreSQL 会自动创建空数据库，需手动执行 DDL：

```bash
# 方式一：通过 docker exec
docker compose exec db psql -U plm -d plm_unified -f /dev/stdin < backend/sql/init.sql

# 方式二：本地 psql（需已安装）
psql postgresql://plm:plmpass@localhost:5432/plm_unified -f backend/sql/init.sql
```

---

## 七、验证转换服务

```bash
# 查看 conversion 日志，确认 Kafka 消费者已就绪
docker compose logs conversion | grep -E "started|CONVERT|Kafka"

# 触发测试转换（需要后端运行中）
# 1. 登录获取 token
# 2. 创建零件并签出
# 3. 上传一个 .stp 文件
# 4. 轮询 /api/workspaces/{ws}/parts/{num}-{ver}/iterations/{iter}/conversion
```

---

## 八、常见问题

### db 容器健康检查一直失败

```bash
# 查看 db 日志
docker compose logs db

# 通常是 PostgreSQL 初始化慢，等待 30s 后重试
docker compose restart backend
```

### conversion 构建失败（wheels 缺失）

```bash
# 确认 LFS 文件已拉取
ls conversion/wheels/*.whl | wc -l   # 期望 22
git lfs pull
```

### Kafka 消息未被消费

```bash
# 检查 conversion 是否已连接到 kafka
docker compose logs conversion | grep "kafka"
# 确认 kafka broker 已就绪
docker compose logs kafka | grep "started"
```

---

## 认证（JWT）

后端启动要求环境变量 `JWT_SECRET` **≥32 字符**，否则启动即报错（`security.py` 在导入时断言）。本地默认值见 `docker/docker-compose.yml`（仅供开发）。生产环境请用强随机值：

```bash
openssl rand -hex 32
```

**种子账号**：用户名 `admin` / 密码 `admin12345`（由迁移 `0002_seed_admin` 插入到默认工作空间，**首次登录后请改密**）。

登录示例：

```bash
curl -X POST http://localhost:8010/api/auth/token \
  -d "username=admin&password=admin12345"
# 返回 {access_token, refresh_token, token_type}
```

---

*最后更新：2026-06-29*
