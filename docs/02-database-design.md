# 02 · Database Design

PostgreSQL is the heart of this project. This document defines the schema, keys,
indexes, and the reasoning behind each — which is worth 20% of the grade.

## ER diagram

```
organizations ──1:N──▶ projects ──1:N──▶ queues ──1:N──▶ jobs ──1:N──▶ job_executions
      │                                     │                │
      └──1:N──▶ users                       │                ├──1:N──▶ job_logs
                                            │                └──1:1──▶ dead_letter_queue (when dead)
                                    retry_policies                │
                                            ▲                      │
                                            └────── queue uses ────┘
                                                                assigned
   workers ──1:N──▶ worker_heartbeats                          worker_id ──▶ workers
   workers ──assigned to──▶ job_executions
   scheduled_jobs (cron/delayed templates) ──spawn──▶ jobs
```

## Tables

### Identity & tenancy
| Table | Purpose | Key columns |
|-------|---------|-------------|
| `organizations` | Top-level tenant | `id (PK)`, `name`, `created_at` |
| `users` | Accounts, belong to an org | `id (PK)`, `org_id (FK)`, `email (unique)`, `password_hash`, `role` |
| `projects` | Owned by an org; owns queues | `id (PK)`, `org_id (FK)`, `name`, `created_at` |

### Queues & policy
| Table | Purpose | Key columns |
|-------|---------|-------------|
| `queues` | A named work channel | `id (PK)`, `project_id (FK)`, `name`, `priority`, `concurrency_limit`, `is_paused`, `retry_policy_id (FK)` |
| `retry_policies` | Reusable retry config | `id (PK)`, `strategy (fixed\|linear\|exponential)`, `base_delay_s`, `max_attempts`, `max_delay_s` |

### Jobs & execution
| Table | Purpose | Key columns |
|-------|---------|-------------|
| `jobs` | A unit of work | `id (PK)`, `queue_id (FK)`, `type`, `payload (jsonb)`, `status`, `priority`, `run_at`, `attempts`, `max_attempts`, `dedup_key`, `worker_id (FK,null)`, `claimed_at`, timestamps |
| `job_executions` | One attempt at a job | `id (PK)`, `job_id (FK)`, `attempt_no`, `worker_id (FK)`, `status`, `started_at`, `finished_at`, `duration_ms`, `error` |
| `job_logs` | Structured log lines | `id (PK)`, `job_id (FK)`, `execution_id (FK)`, `ts`, `level`, `message` |
| `dead_letter_queue` | Permanently failed jobs | `id (PK)`, `job_id (FK, unique)`, `reason`, `failed_at`, `last_error` |
| `scheduled_jobs` | Cron/delayed templates | `id (PK)`, `queue_id (FK)`, `type`, `payload`, `cron_expr`, `next_run_at`, `is_active` |

### Workers & liveness
| Table | Purpose | Key columns |
|-------|---------|-------------|
| `workers` | A worker process instance | `id (PK)`, `name`, `status (online\|draining\|dead)`, `started_at`, `last_heartbeat_at` |
| `worker_heartbeats` | Heartbeat history (audit) | `id (PK)`, `worker_id (FK)`, `ts`, `active_jobs` |

## The job status enum (the state machine)

```
queued · scheduled · claimed · running · completed · failed · dead · cancelled
```

Enforced in the DB as a native `ENUM` type. Transitions are only ever performed inside
transactions in the service layer — never ad-hoc.

## Indexes (performance = marks)

The single most important index — the **hot claim path**, a *partial* index so it stays
small and only covers claimable rows:

```sql
CREATE INDEX idx_jobs_ready
  ON jobs (queue_id, priority DESC, run_at)
  WHERE status IN ('queued', 'scheduled');
```

Others:
```sql
CREATE UNIQUE INDEX idx_jobs_dedup ON jobs (queue_id, dedup_key)
  WHERE dedup_key IS NOT NULL;              -- idempotent submission
CREATE INDEX idx_executions_job ON job_executions (job_id, attempt_no);
CREATE INDEX idx_logs_job ON job_logs (job_id, ts);
CREATE INDEX idx_workers_heartbeat ON workers (last_heartbeat_at)
  WHERE status = 'online';                  -- reaper scan
CREATE INDEX idx_scheduled_due ON scheduled_jobs (next_run_at) WHERE is_active;
```

## Normalization & the one deliberate denormalization

- Config data is **3NF** — no duplicated queue/policy attributes.
- **Exception:** queue throughput/stats are read constantly by the dashboard but derived
  from a huge `job_executions` table. We keep **maintained counters** (or a periodically
  refreshed materialized view) for `queued/running/completed/failed` counts per queue.
  This trades a little write cost for cheap dashboard reads — a conscious choice, not an
  accident. Documented in `06-design-decisions.md`.

## Cascading behaviour

| Relationship | On delete | Why |
|--------------|-----------|-----|
| org → projects → queues → jobs | `CASCADE` | Deleting a project should clean up its work. |
| job → job_executions, job_logs | `CASCADE` | Executions/logs are meaningless without the job. |
| queue → retry_policies | `RESTRICT` | A policy may be shared; don't delete out from under a live queue. |
| job → worker (`worker_id`) | `SET NULL` | A dead worker shouldn't delete job history. |

## Concurrency & integrity guarantees

- **Atomic claim** via `FOR UPDATE SKIP LOCKED` (see `03-concurrency-and-reliability.md`).
- **Idempotent submission** via the partial unique index on `(queue_id, dedup_key)`.
- **Optimistic transitions**: claim uses a `WHERE status='queued'` guard so a lost race
  is a no-op, never a double-run.
- All timestamps `timestamptz`, stored in UTC.

## Performance considerations

- Partial indexes keep the claim scan tiny even with millions of completed jobs.
- `job_logs` is the fastest-growing table → candidate for **time partitioning** and a
  retention job at scale (noted as future work).
- `payload` is `jsonb` for flexibility; we index it only if querying by payload fields
  becomes a real need (YAGNI until then).
