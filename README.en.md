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
- **Mandatory admin bootstrap on first deploy**: until an admin exists, every endpoint except the setup endpoints returns 403, and the frontend forces the setup page
- **Minimal sign-up**: regular users register with only a username + password — no phone number or verification code required
- **Admin user management**: search, filter, ban / unban users (reason required, audit-logged), with guards against banning yourself or other admins
- **Mobile-first**: H5 compatible with browser / Android / iOS

## 🧩 Core Concepts

| Concept | Description |
|---|---|
| `supplier` | Contributes idle GPU compute and earns by compute duration |
| `demander` | Publishes inference / training / batch tasks and consumes points |
| `admin` | Platform governance, configuration, auditing, user management |
| `balance_points` | Freely spendable point balance |
| `reserve_points` | Locked into the shared pool at settlement, used for queuing and interest distribution |
| `frozen_points` | Pre-authorized budget when publishing a task |
| Reserve contribution ratio | `reserve_points / total_earned`, determines scheduling priority |
| Reserve interest | Redistributed to contributors proportional to holdings, compounding into reserve points |

The point unit is "cent" (分); the default minimum settlement unit is 1000 cents (i.e. 10 points). The platform fee is 0 by default (basis points), for pure peer-to-peer exchange.

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI · SQLAlchemy 2.0 (async) · PostgreSQL (asyncpg) · Redis · MinIO · JWT + Argon2 · APScheduler |
| Frontend | Vue 3 · Vite · TypeScript · Pinia · Vue Router · Tailwind CSS |
| Node Agent | Python · psutil · httpx (hardware probing / task execution / result reporting) |

## 📁 Repository Structure

```
ComputeMarketP2P/
├── backend/                 # FastAPI control plane (API / services / models / migrations / scheduled jobs)
│   ├── app/api/v1/          # Routers: auth / supplier / demand / settlements / account / admin
│   ├── app/services/        # Business logic: auth / account / node / task / settlement / scheduler / audit / admin
│   ├── app/models/          # SQLAlchemy models (defined centrally)
│   └── alembic/versions/    # Database migration scripts
├── frontend/                # Vue 3 mobile H5 (browser / Android / iOS)
├── agent/                   # Compute node agent (deployed on supplier machines)
├── docker-compose.yml       # Orchestration (PostgreSQL / Redis / MinIO / backend / frontend)
└── docker-compose.override.yml  # Local port overrides (avoid clashing with host middleware)
```

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker & Docker Compose (optional, for one-command dependencies)

### Option 1: Docker Compose (recommended)

```bash
docker compose up -d
```

Starts PostgreSQL, Redis, MinIO, backend (`:8000`), and frontend (`:5173`). Database tables are auto-created on startup, and the GPU spec library is pre-seeded.

On first launch, visiting http://localhost:5173 **redirects to the admin setup page**; the system becomes usable only after an admin username and password are set.

> **Port overrides**: if PostgreSQL / Redis / MinIO are already running via Homebrew on the host, `docker-compose.override.yml` remaps host ports to `5433` (PostgreSQL), `6378` (Redis), and `9002` / `9003` (MinIO API / Console) to avoid conflicts.

> **Data persistence**: database and object storage live in the named volumes `pgdata` / `minio_data`. `docker compose down` keeps the data; **only** `docker compose down -v` removes the volumes and wipes the data.

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

## 🔐 Accounts & Bootstrap

| Scenario | Endpoint | Notes |
|---|---|---|
| Check whether setup is needed | `GET /api/v1/auth/setup-status` | Returns `{"need_setup": true/false}`; `true` when no admin exists |
| Bootstrap the first admin | `POST /api/v1/auth/setup` | Only available while no admin exists; returns tokens on success |
| Regular user sign-up | `POST /api/v1/auth/register` | Requires only `username` + `password` (optional `nickname`) |
| Login | `POST /api/v1/auth/login` | `contact` accepts username / phone / email |

> Before the admin bootstrap completes, the backend blocks every request except `setup-status` and `setup` (returns 403).

## 👤 Admin Console

Admin pages live under `/admin` and are accessible to the `admin` role only:

| Module | Route | Capabilities |
|---|---|---|
| Dashboard | `/admin` | Overview (online nodes, pending tasks, today's fee, fee rate) |
| Nodes | `/admin/nodes` | Inspect nodes, force offline |
| Tasks | `/admin/tasks` | Inspect tasks, cancel scheduling |
| Users | `/admin/users` | Keyword search (username / phone / email / nickname), role & status filters, ban / unban (reason required, audit-logged) |
| Audit logs | `/admin/audit` | Query logs, verify hash-chain integrity |
| Platform config | `/admin/config` | Fee rate, settlement unit, retry / timeout thresholds, reserve governance params |

**User management safety rules**: you cannot ban yourself or another admin; banned users are rejected at login and on every API call; phone numbers are masked (first 3 + last 4 digits only).

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

Backend (the project uses the conda environment `GPUSharingP2`; run `conda activate GPUSharingP2` first):

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

## License

No open-source license is specified yet.