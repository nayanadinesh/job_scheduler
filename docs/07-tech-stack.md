# 07 · Tech Stack

## Choices & rationale

| Layer | Choice | Rationale |
|-------|--------|-----------|
| API framework | **FastAPI** | Async-native, minimal boilerplate, auto OpenAPI docs (a deliverable for free). |
| Validation | **Pydantic v2** | Declarative request/response schemas; strong code-quality signal. |
| Language | **Python 3.12** | Team strength; excellent for I/O-bound concurrency here. |
| Database | **PostgreSQL 16** | `FOR UPDATE SKIP LOCKED`, partial indexes, jsonb, `timestamptz`. The whole design leans on it. |
| ORM | **SQLAlchemy 2.0 (async)** | Mature, typed, async sessions; escape-hatch to raw SQL for the claim query. |
| Migrations | **Alembic** | Versioned schema — the migrations deliverable. |
| Worker/Scheduler | **asyncio** (+ `croniter`) | Concurrency without the GIL mattering; cron parsing via a tiny lib. |
| Auth | **python-jose + passlib[bcrypt]** | Standard JWT + password hashing. |
| Settings | **pydantic-settings** | 12-factor env config, validated at startup. |
| Frontend | **React + Vite + TanStack Query** | Fast dev, first-class server-state caching, polling→WS. |
| Charts | **Recharts** (or uPlot for density) | Throughput/health visualization. |
| Tests | **pytest + pytest-asyncio + testcontainers** | Real Postgres in tests — mandatory for concurrency correctness. |
| Lint/format | **ruff + black + mypy** | Clean, typed code (matters to a code-review company). |
| Containerization | **Docker + docker-compose** | One-command setup deliverable. |

## The concurrency question (why Python is fine)

Python's GIL is **irrelevant to this system's correctness and throughput**:

1. **Parallelism across processes** — run N worker processes; each is its own OS process
   with its own GIL. This is how Celery/Gunicorn scale Python.
2. **Coordination in the database** — the atomic claim happens in Postgres
   (`SKIP LOCKED`), guaranteeing no double-claim regardless of language.
3. **asyncio within a worker** — simulated jobs are I/O-bound (`await sleep`), so one
   worker multiplexes many concurrently with no GIL contention.

The GIL only constrains CPU-bound pure-Python loops in a single process — which this
workload does not have.

## Scalable alternatives (documented, not built in v1)

| Pressure | Upgrade |
|----------|---------|
| >1–2k jobs/s | Redis Streams / NATS JetStream broker with push delivery |
| Worker fleet ops (retries, monitoring) | Celery or `arq` |
| Scheduler HA | Multiple schedulers + Postgres advisory-lock leader election |
| Hot single queue | Queue sharding (`shard_id` column, workers claim by shard) |
| `job_logs` growth | Time-partitioned tables + retention job |
| Metrics at scale | Push to Prometheus + Grafana instead of DB counters |

Naming *when* to reach for each — and deliberately not building them yet (YAGNI) — is
itself part of the engineering story.

## Local ports (defaults)

| Service | Port |
|---------|------|
| API (uvicorn) | 8000 |
| PostgreSQL | 5432 |
| Frontend (Vite) | 5173 |
