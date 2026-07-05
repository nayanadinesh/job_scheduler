# 03 · Concurrency & Reliability

This is the crown jewel of the project (worth 15% directly, and underpins the
architecture and backend marks too). Everything here answers one question:

> With many workers running against the same queues, how do we guarantee **no job is
> ever run twice** and **no job is ever lost** — even when workers crash?

## 1. Atomic job claim (`FOR UPDATE SKIP LOCKED`)

The core primitive. One SQL statement claims exactly one ready job for one worker, and
is safe under any number of concurrent workers:

```sql
UPDATE jobs
   SET status = 'claimed', worker_id = :worker_id, claimed_at = now()
 WHERE id = (
       SELECT id FROM jobs
        WHERE queue_id = :queue_id
          AND status = 'queued'
          AND run_at <= now()
        ORDER BY priority DESC, run_at
          FOR UPDATE SKIP LOCKED      -- locked rows are skipped, not waited on
        LIMIT 1
 )
RETURNING *;
```

**Why it works:** `FOR UPDATE` locks the selected row; `SKIP LOCKED` means a second
worker running the same query simply skips the locked row and grabs the next one. No two
workers can ever select the same row. No application-level locking, no race window.

## 2. The worker loop

```python
async def worker_loop(worker_id: str):
    await register_worker(worker_id)
    sem = asyncio.Semaphore(queue.concurrency_limit)   # per-queue cap
    async with asyncio.TaskGroup() as tg:
        tg.create_task(heartbeat_loop(worker_id))      # every HEARTBEAT_INTERVAL
        while not shutting_down:
            if queue.is_paused:
                await asyncio.sleep(POLL_INTERVAL); continue
            job = await claim_one(worker_id, queue.id)  # SKIP LOCKED query above
            if job is None:
                await asyncio.sleep(POLL_INTERVAL)       # nothing ready → back off
                continue
            await sem.acquire()
            tg.create_task(run_job(job, worker_id, sem))  # concurrent execution
    await release_claims(worker_id)                       # graceful shutdown
```

`run_job` transitions `claimed → running`, opens a `job_executions` row, runs the
handler, streams logs, and finalizes to `completed` or triggers the failure path.

## 3. Heartbeats + the reaper (crash recovery)

A worker can die mid-job (crash, OOM, `kill -9`). Its job is stuck in `running` with no
one working on it. We recover automatically:

- Every worker updates `workers.last_heartbeat_at` every `HEARTBEAT_INTERVAL` (e.g. 5s).
- The **reaper** (a periodic task) finds jobs that are `claimed`/`running` whose worker's
  `last_heartbeat_at` is older than the **visibility timeout** (e.g. 30s), and requeues
  them (`status='queued'`, clear `worker_id`, increment `attempts`).

```sql
-- reaper: requeue jobs whose worker went silent
UPDATE jobs SET status='queued', worker_id=NULL
 WHERE status IN ('claimed','running')
   AND worker_id IN (
       SELECT id FROM workers
        WHERE last_heartbeat_at < now() - interval '30 seconds');
```

**Proof test:** submit a long `hang` job, `kill -9` the worker, assert the reaper
requeues it and another worker completes it.

## 4. Retry strategies + backoff

On handler failure, the retry decision uses the queue's `retry_policy`:

| Strategy | `next_delay(attempt)` |
|----------|-----------------------|
| `fixed` | `base_delay_s` |
| `linear` | `base_delay_s * attempt` |
| `exponential` | `min(base_delay_s * 2**(attempt-1), max_delay_s)` |

Retry = set `status='queued'`, `run_at = now() + next_delay`, `attempts += 1`. The job
naturally re-enters the ready set when its `run_at` passes.

## 5. Dead Letter Queue (DLQ)

When `attempts >= max_attempts`, the job stops retrying: `status='dead'` and a row is
written to `dead_letter_queue` with the last error and reason. It's inspectable in the
dashboard and can be **requeued manually** (resets attempts, back to `queued`).

## 6. Graceful shutdown

On `SIGTERM`/`SIGINT`:
1. Set `shutting_down = True` → stop claiming new jobs.
2. Mark the worker `draining`.
3. Let in-flight tasks finish (bounded grace period).
4. Release any still-claimed jobs back to `queued`.
5. Mark worker `dead`/deregister and exit.

No job is abandoned in an inconsistent state.

## 7. Idempotency & delivery semantics (be honest)

We provide **at-least-once** execution: a job runs one *or more* times (e.g. reaper
requeues a job that actually did finish but crashed before recording it). We do **not**
claim exactly-once — it's impractical without distributed transactions.

To make at-least-once safe:
- **Submission idempotency:** `(queue_id, dedup_key)` unique index prevents duplicate
  enqueues.
- **Execution idempotency (hook):** handlers receive the `job_id`/`execution_id` and are
  encouraged to be idempotent; the design doc explains why this is the right trade-off.

## Tunable constants (config)

| Constant | Default | Meaning |
|----------|---------|---------|
| `POLL_INTERVAL` | 500ms | worker sleep when no work ready |
| `HEARTBEAT_INTERVAL` | 5s | how often workers report liveness |
| `VISIBILITY_TIMEOUT` | 30s | stale threshold before reaper requeues |
| `REAPER_INTERVAL` | 10s | how often the reaper scans |

## The tests that prove reliability

1. **No double execution:** N workers, M jobs → each job's `completed` count is exactly 1.
2. **Crash recovery:** kill a worker mid-job → job completes elsewhere.
3. **Backoff timing:** failed job's next `run_at` matches the policy formula.
4. **DLQ routing:** `always-fails` job lands in DLQ after `max_attempts`.
5. **Graceful shutdown:** SIGTERM releases claims; no orphaned `running` jobs.
