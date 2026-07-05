# 01 · Architecture

## Three logical planes

The system separates into three planes with distinct responsibilities. Keeping them
separate is what makes the architecture legible and testable.

```
                          ┌──────────────────────────────┐
   Dashboard / clients ──▶│         CONTROL PLANE         │
   (REST + WebSocket)     │  FastAPI: auth, projects,     │
                          │  queues, job submission,      │
                          │  config, read APIs, metrics   │
                          └───────────────┬───────────────┘
                                          │ read/write
                                          ▼
                          ┌──────────────────────────────┐
                          │          PostgreSQL           │
                          │       (source of truth)       │
                          │  jobs, executions, workers,   │
                          │  heartbeats, logs, DLQ …       │
                          └───────┬───────────────┬───────┘
                       promote    │               │  claim / heartbeat / update
                       when due    ▼               ▼
              ┌────────────────────────┐  ┌────────────────────────────┐
              │    SCHEDULING PLANE    │  │      EXECUTION PLANE        │
              │  scheduler process:    │  │  worker pool (N processes): │
              │  promotes delayed &    │  │  poll → claim (SKIP LOCKED) │
              │  cron/scheduled jobs   │  │  → run → retry/DLQ          │
              │  into the ready set    │  │  → heartbeat → shutdown     │
              └────────────────────────┘  └────────────────────────────┘
```

### 1. Control plane — the API (`app/api`)
Handles everything a human or client application asks for: authentication, project and
queue management, job submission, configuration, and all read/observability endpoints.
It **never executes jobs** — it only records intent and reports state. Stateless, so it
scales horizontally behind a load balancer.

### 2. Scheduling plane — the scheduler (`app/scheduler`)
A single logical process that wakes periodically and **promotes** jobs whose time has
come: delayed jobs past their `run_at`, cron jobs due to fire (computes the next
occurrence and enqueues a concrete job), and scheduled one-offs. It turns "future work"
into "ready work" and nothing else.

> **Scaling note:** one active scheduler avoids duplicate cron fires. To run more than
> one for HA, use a Postgres advisory lock for leader election (documented as a scalable
> alternative in `06-design-decisions.md`, not built in v1).

### 3. Execution plane — the workers (`app/worker`)
The muscle. Each worker process loops: poll a queue, **atomically claim** one ready job
(`FOR UPDATE SKIP LOCKED`), run it up to the queue's concurrency limit, emit heartbeats,
persist the result, and on failure schedule a retry or route to the DLQ. Workers are
identical, stateless, and disposable — the whole reliability story lives here and in the
database.

## Why the database is the coordinator

We deliberately use **PostgreSQL itself** as the coordination layer instead of a
dedicated broker (Redis/RabbitMQ) for v1:

- The atomic claim (`SELECT … FOR UPDATE SKIP LOCKED`) gives us exactly the "no two
  workers grab the same job" guarantee a broker would — with full transactional
  integrity alongside the job's data.
- One system to run, back up, and reason about. KISS.
- It demonstrates that we understand the *mechanics* of a queue, not just how to import
  a library.

When throughput outgrows Postgres polling (~1–2k jobs/s), the migration path to Redis
Streams / NATS JetStream is documented — see `06-design-decisions.md`.

## Request → execution flow (happy path)

1. Client `POST /api/v1/queues/{id}/jobs` → API validates, inserts a `jobs` row
   (`status=queued`, `run_at=now`), returns `202` with the job id.
2. A worker's poll finds it, atomically flips it to `claimed`, then `running`, and
   creates a `job_executions` row (attempt 1).
3. Worker runs the handler, streaming progress into `job_logs`, heartbeating throughout.
4. On success → `completed`, execution row closed with metrics. On failure → retry is
   scheduled (`status=queued`, future `run_at`) or the job goes to the DLQ.
5. Dashboard reflects every transition via polling (v1) or WebSocket push (bonus).

## Component / directory layout

```
app/
├── main.py            # FastAPI app factory, router wiring
├── config.py          # settings via pydantic-settings (env-driven)
├── db.py              # async engine, session factory
├── models/            # SQLAlchemy models (one file per aggregate)
├── schemas/           # Pydantic request/response models
├── api/               # routers: auth, projects, queues, jobs, workers, dlq, metrics
├── services/          # business logic (claim, retry, promote, requeue)
├── worker/            # worker loop, handlers, heartbeat, reaper, shutdown
├── scheduler/         # cron/delayed promotion loop
└── core/              # security (JWT), errors, logging, pagination
alembic/               # migrations
tests/                 # unit + integration + concurrency tests
web/                   # React dashboard
docker-compose.yml
```

## Non-goals (scope discipline)

- Not a general workflow engine (basic dependency chaining is a bonus, not the core).
- Not exactly-once delivery — we provide **at-least-once + idempotency hooks** and say so.
- Not multi-region. Single Postgres, single region.
