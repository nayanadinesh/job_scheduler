# Distributed Job Scheduler

A production-inspired platform that reliably executes asynchronous background jobs
across multiple workers. Built for the Codity.ai intern assignment.

> **One-line summary:** submit background jobs (now / later / cron), and a fleet of workers
> atomically claims and runs them — with retries, exponential backoff, dead-letter queuing,
> heartbeats, a reaper, and a live React dashboard.

---

## Quick start (Docker)

```bash
# Start everything: Postgres + API (with migrations) + 2 workers + frontend
docker compose up

# API:      http://localhost:8000
# Swagger:  http://localhost:8000/docs
# Dashboard: http://localhost:5173
```

## Quick start (local dev)

```bash
# 1. Install backend deps
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 2. Start Postgres
docker compose up -d db

# 3. Migrate
alembic upgrade head

# 4. Run API
uvicorn app.main:app --reload

# 5. Run a worker (separate terminal)
python -m app.worker

# 6. Run the frontend (separate terminal)
cd frontend && npm install && npm run dev
```

## Run tests

```bash
# Full suite with coverage (requires no Postgres — uses SQLite in-memory)
pytest tests/ -v

# With coverage report
pytest tests/ --cov=app --cov-report=html
```

Coverage: **97%** across 74 tests.

---

## Tech stack

| Layer | Choice |
|---|---|
| API | FastAPI + Pydantic v2 |
| Database | PostgreSQL (SQLite for tests) |
| ORM | SQLAlchemy 2.0 async + Alembic |
| Worker | asyncio pool with semaphore-bound concurrency |
| Auth | JWT (python-jose + bcrypt) |
| Frontend | React + Vite + TanStack Query |
| Scheduler | asyncio loop + croniter |

## Key design decisions

### Atomic job claiming (`FOR UPDATE SKIP LOCKED`)

Workers claim jobs atomically using a SELECT with `FOR UPDATE SKIP LOCKED` on
PostgreSQL — a single SQL statement that locks a row and skips already-locked ones.
This prevents double-execution without any application-level locking.

### At-least-once delivery via `dedup_key`

Callers may pass a `dedup_key`; a partial unique index on `(queue_id, dedup_key)`
(where `status != 'dead'`) prevents duplicate queuing for idempotent jobs.

### Heartbeats + reaper

Each worker writes a heartbeat every 5s. A reaper loop runs every 10s and requeues
any `running` jobs owned by workers whose heartbeat is older than `visibility_timeout_s`
(default: 30s), recovering from crashed worker processes automatically.

### Retry strategies

Three strategies (fixed / linear / exponential backoff) with configurable `base_delay`
and `max_delay` per queue. Jobs exceeding `max_attempts` move to `dead` (DLQ) status.

### Delayed + cron jobs

- **Delayed**: `schedule: {kind: "delay", delay_s: 60}` → job created with `status=scheduled`,
  `run_at=now+delay`. A scheduler loop promotes due jobs to `queued` every second.
- **Cron**: `ScheduledJob` templates fire a new `Job` each time `next_run_at` passes.

---

## API surface

| Method | Path | Description |
|---|---|---|
| POST | `/api/v1/auth/register` | Register org + admin user |
| POST | `/api/v1/auth/login` | Get JWT token |
| GET/POST | `/api/v1/projects` | List / create projects |
| GET/POST | `/api/v1/projects/{id}/queues` | List / create queues |
| GET/POST | `/api/v1/queues/{id}/jobs` | List / submit jobs |
| POST | `/api/v1/jobs/{id}/cancel` | Cancel a queued job |
| POST | `/api/v1/jobs/{id}/retry` | Requeue a dead/failed job |
| GET | `/api/v1/jobs/{id}/logs` | Execution logs |
| GET | `/api/v1/queues/{id}/stats` | Per-queue job counts |
| GET/POST | `/api/v1/queues/{id}/scheduled-jobs` | Cron templates |
| DELETE | `/api/v1/scheduled-jobs/{id}` | Delete cron template |
| GET | `/api/v1/metrics` | Org-wide aggregate stats |
| GET | `/api/v1/workers` | Active worker list |

Full interactive docs at `/docs` (Swagger UI, FastAPI-generated).

---

## Documentation

| Doc | Contents |
|---|---|
| [`docs/00-overview.md`](docs/00-overview.md) | Problem, glossary, mental model |
| [`docs/01-architecture.md`](docs/01-architecture.md) | 3-plane architecture |
| [`docs/02-database-design.md`](docs/02-database-design.md) | Schema, indexes, cascades |
| [`docs/03-concurrency-and-reliability.md`](docs/03-concurrency-and-reliability.md) | Atomic claim, heartbeats, reaper, retries, DLQ |
| [`docs/04-api-design.md`](docs/04-api-design.md) | REST conventions, error handling |
| [`docs/05-frontend.md`](docs/05-frontend.md) | Dashboard screens |
| [`docs/06-design-decisions.md`](docs/06-design-decisions.md) | Trade-off analysis |
| [`docs/07-tech-stack.md`](docs/07-tech-stack.md) | Stack choices + scalable alternatives |
| [`docs/08-implementation-plan.md`](docs/08-implementation-plan.md) | Increment-by-increment build plan |
| [`docs/09-git-workflow.md`](docs/09-git-workflow.md) | Git branching strategy |

## Project structure

```
.
├── app/
│   ├── api/            # FastAPI routers (auth, jobs, queues, metrics, workers)
│   ├── core/           # Deps, errors, logging, response envelope, security
│   ├── models/         # SQLAlchemy ORM models
│   ├── schemas/        # Pydantic v2 request/response schemas
│   ├── worker/         # asyncio worker: claimer, executor, retry, heartbeat, pool
│   └── scheduler/      # Scheduler loop + reaper loop
├── alembic/            # Versioned migrations
├── frontend/           # React + Vite dashboard
│   └── src/
│       ├── api/        # Axios client + typed API calls
│       ├── components/ # Layout, UI primitives, metrics, job table
│       └── pages/      # Overview, Queues, Workers, Submit, Login
├── tests/              # pytest suite (74 tests, 97% coverage)
└── docs/               # Architecture + design docs
```
