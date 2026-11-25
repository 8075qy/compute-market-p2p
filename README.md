# ComputeMarketP2P

[English](README.en.md)

去中心化 AI 算力共享市场：让拥有闲置 GPU/NPU 的**供给方**贡献算力，让有推理 / 训练需求的**需求方**按需取用算力，平台负责供需匹配、调度、结算与治理。

> 纯技术互助网络，无金融 / 变现 / 充值属性，积分仅用于平台内算力交换。

## ✨ 特性

- **供需一体**：同一账号可同时作为供给方（贡献算力）与需求方（消费算力）
- **算力时间银行**：结算收益 30% 自动锁定为储备分形成公共池；储备贡献率决定调度优先级，储备分按持仓占比享受复利利息
- **实时扣费 + 暂停 + 恢复**：分段预授权计费，发布任务只冻结预估首段用量，余额不足自动暂停（`PAUSED`），余额恢复自动续跑
- **智能调度**：按显存匹配度、模型缓存命中、储备贡献率、信誉分等综合评分派单
- **批处理任务**：上传数据包，节点动态领取批次，按区间执行并上报进度
- **多卡节点与整机调度**：支持单卡 / 多卡节点，按总显存匹配
- **反作弊**：结果哈希证明、采样复核、算力谎报容差校验、节点防多开 / 防女巫
- **哈希链审计日志**：不可篡改，关键写操作留痕
- **首次部署强制初始化管理员**：未设置管理员前，除初始化接口外所有接口返回 403，前端强制跳转初始化页
- **极简注册**：普通用户仅需用户名 + 密码即可注册，无手机号 / 验证码门槛
- **管理端用户管理**：用户检索、筛选、封禁 / 解封（带原因、写审计日志），禁止封禁自己与其他管理员
- **移动端优先**：H5 同时兼容浏览器 / Android / iOS

## 🧩 核心概念

| 概念 | 说明 |
|---|---|
| 供给方 `supplier` | 贡献闲置 GPU 算力，按算力时长结算收益 |
| 需求方 `demander` | 发布推理 / 训练 / 批处理任务，按量消费积分 |
| 管理员 `admin` | 平台治理、配置、审计、用户管理 |
| 自由分 `balance_points` | 可自由使用的积分余额 |
| 储备分 `reserve_points` | 结算时锁定进公共池，用于互助排队与利息分配 |
| 冻结分 `frozen_points` | 发布任务时预授权的预算额度 |
| 储备贡献率 | `reserve_points / total_earned`，决定调度排队优先级 |
| 储备利息 | 公共池新产出按储备占比返还，计入储备分形成复利 |

积分单位为「分」，默认最小结算单位为 1000 分（即 10 积分）；平台抽成默认 0（万分比），纯对等交换。

## 🛠 技术栈

| 层 | 技术 |
|---|---|
| 后端 | FastAPI · SQLAlchemy 2.0 (async) · PostgreSQL (asyncpg) · Redis · MinIO · JWT + Argon2 · APScheduler |
| 前端 | Vue 3 · Vite · TypeScript · Pinia · Vue Router · Tailwind CSS |
| 节点 Agent | Python · psutil · httpx（硬件探测 / 任务执行 / 结果上报） |

## 📁 仓库结构

```
ComputeMarketP2P/
├── backend/                 # FastAPI 控制面（API / 服务 / 模型 / 迁移 / 定时任务）
│   ├── app/api/v1/          # 路由：auth / supplier / demand / settlements / account / admin
│   ├── app/services/        # 业务逻辑：auth / account / node / task / settlement / scheduler / audit / admin
│   ├── app/models/          # SQLAlchemy 模型（集中定义）
│   └── alembic/versions/    # 数据库迁移脚本
├── frontend/                # Vue 3 移动端 H5（浏览器 / Android / iOS）
├── agent/                   # 算力节点代理（部署在供给方机器）
├── docker-compose.yml       # 容器编排（PostgreSQL / Redis / MinIO / 后端 / 前端）
└── docker-compose.override.yml  # 本地端口覆盖（避免与宿主机中间件冲突）
```

## 🚀 快速开始

### 前置要求

- Python 3.11+
- Node.js 18+
- Docker & Docker Compose（可选，用于一键拉起依赖）

### 方式一：Docker Compose（推荐）

```bash
docker compose up -d
```

一键启动 PostgreSQL、Redis、MinIO、后端（`:8000`）与前端（`:5173`）。数据表在服务启动时自动创建，并预置 GPU 规格库。

启动后首次访问前端 http://localhost:5173 会**自动跳转管理员初始化页**，设置管理员用户名与密码后系统方可使用。

> **端口覆盖**：若宿主机已用 Homebrew 启动 PostgreSQL / Redis / MinIO，`docker-compose.override.yml` 会把宿主机端口改为 `5433`（PostgreSQL）、`6378`（Redis）、`9002` / `9003`（MinIO API / Console），避免端口冲突。

> **数据持久化**：数据库与对象存储数据存放在命名卷 `pgdata` / `minio_data`。`docker compose down` 保留数据；**只有** `docker compose down -v` 会删除卷并清空数据。

### 方式二：本地手动启动

1. 启动依赖中间件：

```bash
docker compose up -d postgres redis minio
```

2. 启动后端：

```bash
cd backend
cp .env.example .env   # 按需修改数据库 / Redis / MinIO / JWT 配置
pip install -e ".[dev]"
alembic upgrade head   # 可选，服务启动时也会自动建表
python -m uvicorn app.main:app --reload
```

> 后端定时任务（调度 / 心跳 / 重试 / 储备利息）随 uvicorn 进程在 lifespan 内自动启动。

3. 启动前端：

```bash
cd frontend
npm install
npm run dev
```

访问 http://localhost:5173，API 文档见 http://localhost:8000/docs（`DEBUG` 模式）。

4. 部署算力节点 Agent：

```bash
cd agent
cp .env.example .env   # 填写后端地址与供给方账号
pip install -r requirements.txt
python agent.py
```

## 🔐 账号与初始化

| 场景 | 接口 | 说明 |
|---|---|---|
| 查询是否需要初始化 | `GET /api/v1/auth/setup-status` | 返回 `{"need_setup": true/false}`，无管理员时为 `true` |
| 首次初始化管理员 | `POST /api/v1/auth/setup` | 仅在系统无管理员时可用，成功后直接返回登录令牌 |
| 普通用户注册 | `POST /api/v1/auth/register` | 仅需 `username` + `password`（可选 `nickname`） |
| 登录 | `POST /api/v1/auth/login` | `contact` 支持用户名 / 手机号 / 邮箱 |

> 未完成管理员初始化前，后端全局拦截除 `setup-status`、`setup` 之外的所有请求（返回 403）。

## 👤 管理端功能

管理端页面统一在 `/admin` 下，仅 `admin` 角色可访问：

| 模块 | 路由 | 能力 |
|---|---|---|
| 仪表盘 | `/admin` | 平台概览（在线节点、待调度任务、今日抽成、抽成比例） |
| 节点管理 | `/admin/nodes` | 查看节点、强制下线 |
| 任务管理 | `/admin/tasks` | 查看任务、取消调度 |
| 用户管理 | `/admin/users` | 关键词搜索（用户名 / 手机号 / 邮箱 / 昵称）、角色与状态筛选、封禁 / 解封（必填原因、写审计日志） |
| 审计日志 | `/admin/audit` | 查询日志、校验哈希链完整性 |
| 平台配置 | `/admin/config` | 抽成比例、结算单位、重试 / 超时阈值、储备治理参数 |

**用户管理安全约束**：不能封禁自己，不能封禁其他管理员；封禁后该用户的登录与接口访问都会被拒绝；手机号展示脱敏（仅保留前 3 后 4）。

## ⚙️ 环境变量

关键环境变量（完整模板见 `backend/.env.example`）：

| 变量 | 说明 | 默认值 |
|---|---|---|
| `DATABASE_URL` | PostgreSQL 连接串 | `postgresql+asyncpg://dev:dev@localhost:5432/compute_market_p2p` |
| `REDIS_URL` | Redis 连接串 | `redis://localhost:6379/0` |
| `MINIO_ENDPOINT` / `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` | MinIO 对象存储 | `localhost:9000` / `minioadmin` / `minioadmin` |
| `JWT_SECRET` | JWT 签名密钥（生产务必更换，≥32 字符） | 开发占位值 |
| `CORS_ORIGINS` | 允许跨域来源 | `["http://localhost:5173", "http://localhost:8080"]` |

平台治理参数（准备金率 `reserve_ratio=30%`、储备利息 `reserve_interest_ratio=50%`、单人借用上限 `max_borrow_ratio=20%`、预授权窗口 `PREAUTH_MINUTES=60` 等）见 `backend/app/core/config.py` 与数据库 `platform_config` 表。

## 🧪 测试与检查

后端（项目统一使用 conda 环境 `GPUSharingP2`，可先 `conda activate GPUSharingP2`）：

```bash
cd backend
python -m pytest tests/ -v   # 单元测试
python -m ruff check .       # 代码检查
python -m mypy app           # 类型检查
```

前端：

```bash
cd frontend
npm run build                # vue-tsc 类型检查 + 构建
npm run test:unit            # 单元测试
```

## 许可证

本项目暂未指定开源许可证。