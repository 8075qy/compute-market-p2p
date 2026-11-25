# ComputeMarketP2P

[中文](README.md)

A decentralized AI compute-sharing marketplace: **suppliers** contribute idle GPU/NPU compute, **demanders** consume compute on demand for inference / training, and the platform handles matching, scheduling, settlement, and governance.

> A purely technical mutual-aid network with no financial, cash-out, or top-up attributes. Points are used only for compute exchange within the platform.

## ✨ Features

- **Unified supply & demand**: one account can act as both a supplier (contribute compute) and a demander (consume compute)
- **Compute Time Bank**: 30% of settlement earnings are automatically locked as reserve points into a shared pool; reserve contribution ratio determines scheduling priority, and reserve points earn compound interest proportional to holdings
- **Real-time billing + pause + resume**: segmented pre-authorization billing — publishing a task only freezes the estimated first segment, auto-pauses (`PAUSED`) when balance is insufficient, and auto-resumes once balance is restored
- **Smart scheduling**: dispatches by combined scoring of VRAM fit, model-cache hit, reserve contribution ratio, reputation, and more
- **Batch tasks**: upload a data package, nodes dynamically claim batches, execute by range, and report progress
- **Multi-GPU nodes & whole-machine scheduling**: supports single- / multi-GPU nodes matched by total VRAM
- **Anti-cheat**: result hash proofs, sampled verification, compute over-reporting tolerance checks, and anti-multi-registration / anti-Sybil node limits
- **Hash-chained audit logs**: tamper-evident, recording all critical writes
- **Mobile-first**: H5 compatible with browser / Android / iOS

## 🧩 Core Concepts

| Concept | Description |
|---|---|
| `supplier` | Contributes idle GPU compute and earns by compute duration |
| `demander` | Publishes inference / training / batch tasks and consumes points |
| `admin` | Platform governance, configuration, and auditing |
| `balance_points` | Freely spendable point balance |
| `reserve_points` | Locked into the shared pool at settlement, used for queuing and interest distribution |
| `frozen_points` | Pre-authorized budget when publishing a task |
| Reserve contribution ratio | `reserve_points / total_earned`, determines scheduling priority |
| Reserve interest | Redistributed to contributors proportional to holdings, compounding into reserve points |

The point unit is "cent" (分); the default minimum settlement unit is 1000 cents (i.e., 10 points). The platform fee is 0 by default (basis points), for pure peer-to-peer exchange.

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI · SQLAlchemy 2.0 (async) · PostgreSQL (asyncpg) · Redis · MinIO · JWT + Argon2 · APScheduler |
| Frontend | Vue 3 · Vite · TypeScript · Pinia · Vue Router · Tailwind CSS |
| Node Agent | Python · psutil · httpx (hardware probing / task execution / result reporting) |

## 📁 Repository Structure

```
ComputeMarketP2P/
├── backend/      # FastAPI control plane (API / services / models / migrations / scheduled jobs)
├── frontend/     # Vue 3 mobile H5 (browser / Android / iOS)
├── agent/        # Compute node agent (deployed on supplier machines)
├── docs/         # Requirements / architecture / API / flows / anti-cheat / deployment docs
└── docker-compose.yml  # Local development orchestration
```

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+ (frontend)
- Docker & Docker Compose (optional, for one-command dependencies)

### Option 1: Docker Compose (recommended)

```bash
docker compose up -d
```

Starts PostgreSQL, Redis, MinIO, backend (`:8000`), and frontend (`:5173`). Database tables are auto-created on startup, and the GPU spec library is pre-seeded.

### Option 2: Manual local startup

1. Start the dependency middleware:

```bash
docker compose up -d postgres redis minio
```

2. Start the backend:

```bash
cd backend
cp .env.example .env   # Adjust database / Redis / MinIO / JWT as needed
pip install -e ".[dev]"
alembic upgrade head   # Optional; tables are also auto-created on startup
python -m uvicorn app.main:app --reload
```

> Backend scheduled jobs (scheduler / heartbeat / retry / reserve interest) start automatically within the uvicorn lifespan.

3. Start the frontend:

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173; the API docs are at http://localhost:8000/docs (`DEBUG` mode).

4. Deploy the compute node agent:

```bash
cd agent
cp .env.example .env   # Fill in the backend URL and supplier account
pip install -r requirements.txt
python agent.py
```

## ⚙️ Environment Variables

Key environment variables (full template in `backend/.env.example`):

| Variable | Description | Default |
|---|---|---|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql+asyncpg://dev:dev@localhost:5432/compute_market_p2p` |
| `REDIS_URL` | Redis connection string | `redis://localhost:6379/0` |
| `MINIO_ENDPOINT` / `MINIO_ACCESS_KEY` / `MINIO_SECRET_KEY` | MinIO object storage | `localhost:9000` / `minioadmin` / `minioadmin` |
| `JWT_SECRET` | JWT signing key (change in production, ≥32 chars) | dev placeholder |
| `CORS_ORIGINS` | Allowed cross-origin origins | `["http://localhost:5173", "http://localhost:8080"]` |

Governance parameters (reserve ratio `reserve_ratio=30%`, reserve interest `reserve_interest_ratio=50%`, per-user borrow cap `max_borrow_ratio=20%`, pre-authorization window `PREAUTH_MINUTES=60`, etc.) are defined in `backend/app/core/config.py` and the `platform_config` table.

## 🧪 Testing & Checks

Backend:

```bash
cd backend
python -m pytest tests/ -v   # unit tests
python -m ruff check .       # lint
python -m mypy app           # type check
```

Frontend:

```bash
cd frontend
npm run build                # vue-tsc type check + build
npm run test:unit            # unit tests
```

## 📚 Documentation

Full requirements, architecture, API, business flows, anti-cheat design, and deployment guide are under [`docs/`](docs/README.md).

## License

No open-source license is specified yet.