# ComputeMarketP2P Backend

去中心化AI算力共享市场后端服务

## 技术栈

- Python 3.11+
- FastAPI
- SQLAlchemy 2.0 (async)
- PostgreSQL + asyncpg
- Redis
- MinIO
- JWT + Argon2
- APScheduler
- Docker SDK

## 安装

项目统一使用 conda 环境 `GPUSharingP2`（Python 3.11）：

```bash
conda activate GPUSharingP2
pip install -e ".[dev]"
```

所有命令（测试 / 启动 / 检查）均在该环境下执行：

```bash
# 运行测试
/opt/homebrew/Caskroom/miniconda/base/envs/GPUSharingP2/bin/python -m pytest tests/ -v

# 启动服务
/opt/homebrew/Caskroom/miniconda/base/envs/GPUSharingP2/bin/python -m uvicorn app.main:app --reload
```

## 运行测试

```bash
python -m pytest tests/ -v
```

## 启动服务

```bash
python -m uvicorn app.main:app --reload
```