# 00 · Overview

## What we are building

A **distributed job scheduler**: a system that reliably runs background tasks across
multiple worker machines. Applications submit "jobs" (units of work) through a REST API;
a pool of workers picks them up, runs them concurrently, and reports results — with
retries, failure handling, and full observability.

Think of it as a **smart, fault-tolerant to-do list for computers**.

## The mental model

```
Application/UI  --submit job-->  API  --stores-->  PostgreSQL  <--claims/updates--  Workers
                                                        ^
                                                        |
                                                   Scheduler (promotes
                                                   delayed/cron jobs when due)
```

- **PostgreSQL is the single source of truth.** Every job, its status, history, and logs
  live there. No hidden in-memory state that dies with a process.
- **Workers are stateless and disposable.** Kill one mid-job and the system recovers.
- **The API never runs jobs itself** — it only enqueues them and reports state.

## What the jobs actually do (important)

The assignment tests the **scheduler**, not business logic. So jobs run **simulated
work**, not real email/video processing:

```json
{ "type": "simulate", "durationMs": 5000, "failRate": 0.3 }
```

A handler that `await asyncio.sleep(durationMs)`, logs progress, and fails at `failRate`.
This is the *correct* way to exercise infrastructure: it lets us demonstrate retries,
backoff, DLQ, and worker-crash recovery **on demand**. The *system* is fully functional;
the *work* is synthetic.

Sample job types we register so every feature is demoable:

| Type            | Behaviour                        | Demonstrates            |
|-----------------|----------------------------------|-------------------------|
| `send-email`    | fast, reliable                   | happy path, throughput  |
| `process-video` | slow (5–10s)                     | long-running, heartbeats|
| `flaky-api`     | fails ~30%                       | retries + backoff       |
| `always-fails`  | always throws                    | Dead Letter Queue       |
| `hang`          | never finishes                   | reaper / visibility timeout |

## The job lifecycle

```
Queued ──▶ Claimed ──▶ Running ──▶ Completed ✅
   ▲                        │
   │                        ├──▶ Failed ──▶ (retry, wait backoff) ──▶ Queued
   │                        │                     │
 Scheduled                  │                     └──▶ (attempts exhausted) ──▶ Dead Letter ☠️
 (delayed/cron,
  promoted when due)
```

## Glossary

| Term | Meaning |
|------|---------|
| **Job** | A unit of work to run once (may retry). Belongs to a queue. |
| **Queue** | A named channel with its own priority, concurrency limit, and retry policy. |
| **Worker** | A process that claims and executes jobs. Many run in parallel. |
| **Claim** | Atomically taking ownership of a job so no other worker runs it. |
| **Heartbeat** | Periodic "I'm alive" signal from a worker. |
| **Reaper** | Background task that requeues jobs whose worker died (stale heartbeat). |
| **Backoff** | Increasing wait between retries (fixed / linear / exponential). |
| **DLQ** | Dead Letter Queue — where permanently-failed jobs are parked for inspection. |
| **Visibility timeout** | How long a claimed job may run before it's considered dead and requeued. |
| **Idempotency** | Running the same job twice has the same effect as once. |

## Who creates jobs?

In production, **applications** enqueue jobs programmatically via REST. The dashboard
offers **manual job creation for testing/demo**, plus full visibility and control
(retry, requeue, pause queues, inspect logs). This distinction is intentional and
documented in [`05-frontend.md`](05-frontend.md).

## Design north star

> Prioritize engineering quality, reliability, and clarity over feature count.
> A rock-solid smaller system beats a buggy feature-complete one.
