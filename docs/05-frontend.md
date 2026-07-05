# 05 · Frontend

An **operations console**, not a marketing page. Visual direction: dense, data-first,
Grafana/Sentry energy. Status colors carry meaning (green = running/healthy,
amber = failed, red = DLQ, grey = idle). Live-pulsing worker dots.

Stack: React + Vite + TanStack Query (server state), polling in v1, WebSocket upgrade as
a bonus. No client-side duplication of server state — the API is the source of truth.

## Who uses it, and how jobs get created

Jobs are normally enqueued **programmatically via REST** by client applications. The
dashboard provides **manual creation for testing/demo**, and — more importantly — full
**observability and control** over the live system. Both roles are first-class.

## Screens

### 1. Overview / Health (landing)
The "is everything okay?" glance: system throughput sparkline, worker count with live
pulse, global counts (queued / running / failed / DLQ), and a card per queue with its
live numbers and pause state.

### 2. Job Explorer (primary screen)
Filterable, paginated table of jobs — the main surface for *managing existing jobs*.
Columns: id, queue, type, status (color chip), attempts, worker, updated. Filters:
queue, status, type, search. Row actions: Retry (failed), Cancel (queued).

Clicking a row opens a **detail drawer**:
- Lifecycle timeline (Queued → Claimed → Running → …), each transition timestamped.
- Execution/attempt history with durations and errors.
- Streamed logs.
- **AI failure summary** (bonus) — plain-English root cause for failed jobs.

### 3. Create Job (form)
Queue selector, type selector, and a `schedule` toggle (immediate / delayed / scheduled /
cron / batch) that reveals the relevant fields. Payload editor exposes `durationMs` and
`failRate` so a demoer can dial up chaos and watch the system respond. Priority + optional
dedup key.

### 4. Queue Config
Per-queue controls: concurrency limit, priority, retry policy (strategy + base delay +
max attempts), and **Pause / Resume**.

### 5. Workers
Live list of worker processes: status, last heartbeat (pulsing = alive), currently
running jobs, uptime.

### 6. Dead Letter Queue
Table of permanently-failed jobs with last error and one-click **Requeue**.

## Manage actions summary

| Action | Where | Effect |
|--------|-------|--------|
| Retry | Job Explorer / detail | re-run a failed job now |
| Cancel | Job Explorer | cancel a still-queued job |
| Requeue | DLQ | revive a dead job |
| Pause / Resume | Queue Config | stop/start a queue draining work |
| Inspect | detail drawer | timeline, logs, AI summary |

## Live updates

- **v1:** TanStack Query polling (`refetchInterval`) on the health, explorer, and worker
  views — simple and robust.
- **Bonus:** subscribe to `/api/v1/ws` and invalidate/patch query caches on push events
  for instant updates without polling churn.

## Accessibility & responsiveness

Keyboard-navigable tables and drawers, visible focus states, color + icon (never color
alone) for status, responsive down to tablet widths. Respects `prefers-reduced-motion`
for the pulsing indicators.
