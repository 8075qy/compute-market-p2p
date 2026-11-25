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
- **移动端优先**：H5 同时兼容浏览器 / Android / iOS

## 🧩 核心概念

| 概念 | 说明 |
|---|---|
| 供给方 `supplier` | 贡献闲置 GPU 算力，按算力时长结算收益 |
| 需求方 `demander` | 发布推理 / 训练 / 批处理任务，按量消费积分 |
| 管理员 `admin` | 平台治理、配置、审计 |
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
├── backend/      # FastAPI 控制面（API / 服务 / 模型 / 迁移 / 定时任务）
├── frontend/     # Vue 3 移动端 H5（浏览器 / Android / iOS）
├── agent/        # 算力节点代理（部署在供给方机器）
├── docs/         # 需求 / 架构 / API / 流程 / 反作弊 / 部署文档
└── docker-compose.yml  # 本地开发环境编排
```

## 🚀 快速开始

### 前置要求

- Python 3.11+
- Node.js 18+（前端）
- Docker & Docker Compose（可选，用于一键拉起依赖）

### 方式一：Docker Compose（推荐）

```bash
docker compose up -d
```

一键启动 PostgreSQL、Redis、MinIO、后端（`:8000`）与前端（`:5173`）。数据表在服务启动时自动创建，并预置 GPU 规格库。

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

后端：

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

## 📚 文档

完整需求、架构、API、业务流程、反作弊与部署方案见 [`docs/`](docs/README.md)。

## 许可证

本项目暂未指定开源许可证。