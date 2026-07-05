# 08 · Implementation Plan

The build proceeds in **small, independently-shippable increments**. Each increment is a
branch → conventional commits → merge to `main` → milestone tag. Ship an increment fully
(code + tests + docs touch-up) before starting the next. Ship increments 0–9 solidly
before touching any bonus.

**Golden rule:** a rock-solid subset beats a buggy feature-complete system. The rubric
rewards reliability and quality, not feature count.

Legend: 🎯 = high-mark area · ⭐ = bonus (only after core is solid)

---

## Increment 0 — Foundation & tooling
**Branch:** `feat/00-foundation`
**Goal:** an empty-but-running skeleton anyone can boot in one command.

- `pyproject.toml` (ruff, black, mypy, pytest), `.env.example`, `config.py`.
- `docker-compose.yml`: Postgres + API.
- FastAPI app factory, `/healthz`, `/readyz`, response-envelope + error middleware.
- `db.py`: async engine/session. Alembic initialized (empty).
- CI-style `make check` (lint + type + test).

**Done when:** `docker compose up` boots, `/healthz` returns ok, `make check` passes.
**Commits:** `chore: scaffold project + tooling`, `feat: app factory + health endpoints`.

---

## Increment 1 — Identity & auth 🎯
**Branch:** `feat/01-auth`
**Goal:** users, orgs, projects, JWT login.

- Models + migration: `organizations`, `users`, `projects`.
- `POST /auth/register`, `/auth/login`, `GET /auth/me`. Password hashing, JWT.
- Projects CRUD, scoped to the authenticated org.
- Tests: register/login flow, auth guard rejects anon, project isolation across orgs.

**Done when:** a user can register, log in, and CRUD their projects; unauth is blocked.

---

## Increment 2 — Queues & retry policies 🎯
**Branch:** `feat/02-queues`
**Goal:** configurable queues.

- Models + migration: `queues`, `retry_policies`.
- Queues CRUD under a project; pause/resume; config (priority, concurrency, policy).
- Validation (concurrency ≥ 1, valid strategy, etc.).
- Tests: CRUD, pause/resume toggles, invalid config rejected.

---

## Increment 3 — Jobs & the state machine 🎯
**Branch:** `feat/03-jobs`
**Goal:** submit and read immediate jobs; lifecycle enum in place.

- Models + migration: `jobs`, `job_executions`, `job_logs`. Status ENUM.
- **Partial index** `idx_jobs_ready` + dedup unique index.
- `POST /queues/{id}/jobs` (immediate only for now), list + filter, `GET /jobs/{id}`.
- Idempotent submission via `dedup_key`.
- Tests: submit → row is `queued`; dedup collision → `409`; filters work.

---

## Increment 4 — Worker & atomic claim 🎯🎯 (the crown jewel)
**Branch:** `feat/04-worker-claim`
**Goal:** first true end-to-end slice — a job runs and completes.

- `app/worker`: worker loop, `claim_one` (`FOR UPDATE SKIP LOCKED`), `run_job`.
- Register a `simulate` handler (`durationMs`, `failRate`) + the sample job types.
- Transitions: `queued → claimed → running → completed`; write `job_executions` + logs.
- Per-queue concurrency semaphore. Add worker to compose (scalable replicas).
- **Tests (critical):** N workers × M jobs → **each job completed exactly once**
  (the no-double-execution test). Uses testcontainers Postgres.

**Done when:** submit a job, a worker runs it, it reaches `completed` with an execution
record — and the concurrency test is green.

---

## Increment 5 — Retries, backoff & DLQ 🎯
**Branch:** `feat/05-retries-dlq`
**Goal:** failures are handled correctly.

- `dead_letter_queue` model + migration.
- Failure path: compute next delay (fixed/linear/exponential), requeue with future
  `run_at`, `attempts++`; on exhaustion → `dead` + DLQ row.
- `POST /jobs/{id}/retry`, `GET /dlq`, `POST /dlq/{job_id}/requeue`.
- Tests: `flaky-api` eventually completes; backoff timing matches formula;
  `always-fails` lands in DLQ after `max_attempts`; requeue revives it.

---

## Increment 6 — Heartbeats, reaper & graceful shutdown 🎯
**Branch:** `feat/06-liveness`
**Goal:** crash recovery.

- Models + migration: `workers`, `worker_heartbeats`.
- Heartbeat loop; reaper task requeues jobs from stale workers (visibility timeout).
- SIGTERM handler: stop claiming, drain in-flight, release claims, deregister.
- Worker read APIs: `GET /workers`, `GET /workers/{id}`.
- Tests: `kill` a worker mid-`hang` job → reaper requeues → completes elsewhere;
  graceful shutdown leaves no orphaned `running` jobs.

---

## Increment 7 — Scheduling: delayed, scheduled, cron, batch 🎯
**Branch:** `feat/07-scheduler`
**Goal:** all five job kinds.

- `scheduled_jobs` model + migration. `app/scheduler` promotion loop (+ `croniter`).
- Extend `POST /jobs` `schedule` union: `delayed`, `scheduled`, `cron`, `batch`.
- Scheduler promotes due jobs into the ready set; cron computes `next_run_at`.
- Tests: delayed job not claimable before `run_at`; cron spawns on schedule (time
  injected/mocked); batch fans out N jobs.

---

## Increment 8 — Observability: metrics, stats, logs 🎯
**Branch:** `feat/08-observability`
**Goal:** the system explains itself.

- Queue stats counters (or materialized view) + `GET /queues/{id}/stats`.
- `GET /metrics` (system throughput/counts), `GET /jobs/{id}/executions` & `/logs`.
- Structured logging with correlation ids across API + workers.
- Tests: stats reflect job outcomes; metrics aggregate correctly.

---

## Increment 9 — Frontend dashboard
**Branch:** `feat/09-dashboard`
**Goal:** the operations console (see `05-frontend.md`).

- Vite + React + TanStack Query app; auth flow; API client.
- Screens: Overview/Health, Job Explorer + detail drawer, Create Job form,
  Queue Config, Workers, DLQ. Polling for live-ish updates.
- A couple of component tests + one Playwright smoke ("dashboard loads, submit job").

**Done when:** you can drive the entire system from the browser.

---

## Increment 10 — Hardening, docs & diagrams
**Branch:** `chore/10-hardening`
**Goal:** submission-ready.

- Fill coverage gaps to the 80% target; finalize the 5 reliability tests.
- Export architecture + ER diagrams (from `01`/`02`) as images.
- Polish README quickstart end-to-end on a clean machine; verify `docker compose up`.
- Proofread `06-design-decisions.md` (the graded doc).

---

## ⭐ Bonus increments (only after 0–10 are solid)

| Branch | Feature | Notes |
|--------|---------|-------|
| `feat/b1-websockets` | WebSocket live updates | push job/worker/queue changes; invalidate query caches |
| `feat/b2-ai-summaries` | **AI failure summaries** | 🎯 the differentiator — LLM root-cause on failed jobs; graceful fallback without an API key. Mirrors Codity's own product. |
| `feat/b3-rbac` | Role-based access control | roles on user; guard mutations |
| `feat/b4-rate-limit` | Rate limiting | per-project submission limits (429) |
| `feat/b5-dag` | Workflow dependencies | jobs wait on parent completion |
| `feat/b6-sharding` | Queue sharding | `shard_id`; workers claim by shard |

**Recommended bonus order:** b2 (AI summaries) → b1 (WebSockets) → b3 (RBAC). The first
two are the most visible and on-brand for Codity.

---

## Definition of Done (every increment)

- [ ] Code + migration for the increment's scope.
- [ ] Tests for the new behavior; `make check` green.
- [ ] Docs touched if behavior/contract changed.
- [ ] Conventional commits; branch merged to `main`; milestone tagged.
- [ ] No secrets committed; `.env.example` updated if config added.

## Milestone tags

`v0.1` after Inc 4 (first job runs) · `v0.2` after Inc 6 (reliable) ·
`v0.3` after Inc 8 (observable) · `v1.0` after Inc 10 (submission-ready).
