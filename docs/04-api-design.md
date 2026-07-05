# 04 · API Design

REST, versioned under `/api/v1`. FastAPI auto-generates OpenAPI/Swagger at `/docs`,
which doubles as our API-documentation deliverable.

## Conventions

- **Response envelope** (consistent across every endpoint):
  ```json
  { "success": true, "data": { }, "error": null, "meta": { } }
  ```
  On error: `success:false`, `data:null`, `error:{ code, message, details }`.
- **Auth:** JWT bearer token. `Authorization: Bearer <token>`.
- **Validation:** Pydantic models reject bad input with `422` + field-level detail.
- **Pagination:** cursor-based; list responses put `next_cursor`, `limit`, `total` in `meta`.
- **Filtering:** query params (`?status=failed&queue_id=...&type=flaky-api`).
- **Errors:** structured, typed codes (e.g. `QUEUE_PAUSED`, `JOB_NOT_FOUND`), never leak
  internals. Every request carries a correlation id in logs.
- **Idempotency:** `POST /jobs` accepts optional `dedup_key`.

## Endpoints

### Auth
```
POST   /api/v1/auth/register        create user + org
POST   /api/v1/auth/login           → { access_token }
GET    /api/v1/auth/me              current user
```

### Projects
```
GET    /api/v1/projects
POST   /api/v1/projects
GET    /api/v1/projects/{id}
PATCH  /api/v1/projects/{id}
DELETE /api/v1/projects/{id}
```

### Queues
```
GET    /api/v1/projects/{id}/queues
POST   /api/v1/projects/{id}/queues        name, priority, concurrency_limit, retry_policy
GET    /api/v1/queues/{id}
PATCH  /api/v1/queues/{id}                  update config
POST   /api/v1/queues/{id}/pause
POST   /api/v1/queues/{id}/resume
GET    /api/v1/queues/{id}/stats            queued/running/completed/failed + throughput
```

### Jobs
```
POST   /api/v1/queues/{id}/jobs             submit a job (see body below)
GET    /api/v1/queues/{id}/jobs             list + filter (status, type, cursor)
GET    /api/v1/jobs/{id}                     full detail
GET    /api/v1/jobs/{id}/executions          attempt history
GET    /api/v1/jobs/{id}/logs                execution logs
POST   /api/v1/jobs/{id}/retry               retry a failed job now
POST   /api/v1/jobs/{id}/cancel              cancel a queued job
```

**Submit body** — one endpoint, `schedule` discriminates the job kind:
```jsonc
{
  "type": "flaky-api",
  "payload": { "durationMs": 3000, "failRate": 0.3 },
  "priority": 5,
  "dedup_key": "optional-idempotency-key",
  "schedule": { "kind": "immediate" }
  // OR { "kind": "delay", "delay_s": 300 }                      // wait N seconds
  // OR { "kind": "scheduled", "run_at": "2026-07-05T09:00:00Z" } // absolute time
  // OR { "kind": "batch", "count": 100, "delay_s": 0 }          // fan out N identical jobs
}
```
Returns `202 Accepted` with the created job — or a **list** of jobs for `batch`.
Batch `dedup_key`s are suffixed per index (`key-0`, `key-1`, …).

**Recurring (cron)** is a separate resource — a reusable template that spawns a
new job on each firing — rather than a one-shot `schedule.kind`:
```
POST   /api/v1/queues/{id}/scheduled-jobs   { name, cron_expr, job_type, job_payload }
GET    /api/v1/queues/{id}/scheduled-jobs
DELETE /api/v1/scheduled-jobs/{id}
```

### Workers (read/observability)
```
GET    /api/v1/workers                       list + status + last heartbeat
GET    /api/v1/workers/{id}                  detail + currently running jobs
```

### Dead Letter Queue
```
GET    /api/v1/dlq                            list dead jobs + filters
POST   /api/v1/dlq/{job_id}/requeue          revive a dead job
```

### Metrics / health
```
GET    /api/v1/metrics                        system-wide throughput, counts
GET    /healthz                               liveness (no auth)
GET    /readyz                                readiness (db reachable)
```

### WebSocket (bonus)
```
WS     /api/v1/ws                             push job/worker/queue state changes
```

## HTTP status usage

| Code | When |
|------|------|
| 200 | successful read/update |
| 201 | resource created (project/queue) |
| 202 | job accepted for async execution |
| 400 / 422 | validation / bad request |
| 401 / 403 | auth / RBAC failure |
| 404 | not found |
| 409 | conflict (e.g. dedup_key collision, queue paused) |
| 429 | rate limited (bonus) |
| 500 | unexpected — logged with correlation id, generic message to client |
