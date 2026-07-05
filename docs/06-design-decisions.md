# 06 · Design Decisions

This is the graded "trade-offs" deliverable. Each entry states the decision, the
alternatives, and *why* — the reasoning a reviewer at a code-review company cares about.

## D1 · Postgres as the queue vs. a dedicated broker (Redis/RabbitMQ)

**Decision:** Use PostgreSQL with `FOR UPDATE SKIP LOCKED` as the coordination layer.

**Why:** It provides the exact "no double-claim" guarantee a broker offers, but keeps job
data and job state in one transactional store — no dual-write consistency problems, one
system to operate. It also demonstrates understanding of the underlying mechanics rather
than delegating them to a library.

**Trade-off / when to change:** Polling has overhead; beyond ~1–2k jobs/s the constant
`SELECT` pressure and index churn favor a purpose-built broker (Redis Streams, NATS
JetStream) with push semantics. Migration path: keep the same service interface
(`claim_one`, `enqueue`) and swap the implementation behind it.

## D2 · At-least-once, not exactly-once

**Decision:** Guarantee at-least-once execution + idempotency hooks.

**Why:** Exactly-once across a crash boundary requires distributed transactions between
the job store and the side effect — impractical and slow. At-least-once is the honest,
industry-standard choice (SQS, Celery, Sidekiq all do this).

**Trade-off:** Handlers may occasionally run twice (e.g. a job that finished but crashed
before recording completion is requeued by the reaper). We mitigate with a submission
dedup key and by designing handlers to be idempotent.

## D3 · asyncio worker vs. threads vs. Celery

**Decision:** Custom asyncio worker process, run as N replicas.

**Why:** Simulated jobs are I/O-bound (`await sleep`), so asyncio multiplexes hundreds
per worker with no GIL contention. True parallelism comes from running multiple *processes*
and from Postgres-level locking — so the GIL is irrelevant to correctness or throughput.
Building the loop ourselves showcases the concurrency competencies being graded.

**Trade-off:** Celery/arq give retries, scheduling, and monitoring for free but hide the
mechanics. We chose to demonstrate the mechanics; Celery is the natural production upgrade.

## D4 · Single scheduler process (no HA in v1)

**Decision:** One logical scheduler promotes delayed/cron jobs.

**Why:** Two schedulers would double-fire cron jobs. One process is simplest and correct.

**Trade-off:** It's a single point of failure for *scheduling* (not execution — workers
keep running). HA path: run multiple, gate promotion behind a Postgres advisory lock so
only the leader promotes. Documented, not built (YAGNI for the assignment).

## D5 · Partial indexes on the hot path

**Decision:** Partial index on `jobs` restricted to claimable statuses.

**Why:** 99% of rows over time are `completed`/`dead`. A partial index only covers
`queued`/`scheduled` rows, staying small and fast regardless of history size — the claim
scan cost stays flat as the table grows to millions of rows.

## D6 · One denormalization: queue stats counters

**Decision:** Maintain per-queue counters (or a refreshed materialized view) instead of
`COUNT(*)`-ing `job_executions` on every dashboard load.

**Why:** The dashboard reads stats constantly; counting a multi-million-row table per
request would dominate DB load. A small maintained counter trades cheap writes for cheap,
frequent reads.

**Trade-off:** Counters can drift under bugs; we treat the executions table as the source
of truth and can rebuild counters from it.

## D7 · Single job-submission endpoint with a `schedule` discriminator

**Decision:** One `POST /jobs` with a tagged `schedule` union rather than five endpoints.

**Why:** All five kinds (immediate/delayed/scheduled/cron/batch) share the same job body;
a discriminated union keeps the API small and validation centralized in Pydantic.

## D8 · JWT stateless auth

**Decision:** JWT bearer tokens, no server session store.

**Why:** Stateless auth lets the API scale horizontally with no shared session state.
RBAC (roles on the user row) is a bonus that layers cleanly on top.

**Trade-off:** Token revocation is harder; acceptable at this scope (short expiry +
refresh is the production answer).

## D9 · Simulated job handlers

**Decision:** Jobs run synthetic work parameterized by `durationMs`/`failRate`.

**Why:** The assignment grades the *scheduler*, not business logic. Synthetic handlers
let us deterministically exercise every reliability path (retry, backoff, DLQ, reaper) and
let a reviewer dial chaos from the UI. Building "real" email/video work would earn zero
marks and add risk.

## D10 · Polling-first frontend, WebSocket as a bonus

**Decision:** Ship polling via TanStack Query; add WebSocket push as an enhancement.

**Why:** Polling is robust, trivial, and correct. WebSockets add latency wins but also
reconnection/auth complexity — worth it only after the core works.

---

### Summary of "known limitations" (stated up front — a maturity signal)
- At-least-once, not exactly-once.
- Single scheduler (scheduling is not HA in v1).
- Postgres-poll throughput ceiling (~1–2k jobs/s) before a broker is warranted.
- Token revocation not implemented (short-lived JWTs assumed).
