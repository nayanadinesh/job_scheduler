"""Aggregate metrics across queues accessible to the current user."""
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.response import ok
from app.db import get_db
from app.models.auth import Project, User
from app.models.job import Job, JobExecution
from app.models.queue import Queue
from app.models.worker import Worker

router = APIRouter(tags=["metrics"])


@router.get("/api/v1/metrics")
async def get_metrics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return aggregate stats across all queues accessible to the current org."""

    # All queue IDs in this org
    queue_rows = (
        await db.execute(
            select(Queue.id, Queue.name)
            .join(Project, Queue.project_id == Project.id)
            .where(Project.org_id == current_user.org_id)
        )
    ).all()
    queue_ids = [r[0] for r in queue_rows]
    queue_names = {r[0]: r[1] for r in queue_rows}

    if not queue_ids:
        return ok({"queues": [], "totals": {}, "workers": {"active": 0, "total": 0}})

    # Per-status counts across all accessible queues
    status_rows = (
        await db.execute(
            select(Job.queue_id, Job.status, func.count(Job.id))
            .where(Job.queue_id.in_(queue_ids))
            .group_by(Job.queue_id, Job.status)
        )
    ).all()

    all_statuses = ("queued", "scheduled", "running", "completed", "failed", "dead", "cancelled")
    per_queue: dict[str, dict] = {qid: {s: 0 for s in all_statuses} for qid in queue_ids}
    for qid, status, count in status_rows:
        if status in per_queue[qid]:
            per_queue[qid][status] = count

    # Average execution duration per queue (completed jobs only)
    dur_rows = (
        await db.execute(
            select(
                Job.queue_id,
                func.avg(JobExecution.duration_ms),
                func.count(JobExecution.id),
            )
            .join(Job, JobExecution.job_id == Job.id)
            .where(Job.queue_id.in_(queue_ids), JobExecution.status == "completed")
            .group_by(Job.queue_id)
        )
    ).all()
    avg_duration: dict[str, float | None] = {r[0]: round(float(r[1]), 1) if r[1] else None for r in dur_rows}
    exec_count: dict[str, int] = {r[0]: r[2] for r in dur_rows}

    queues_out = []
    totals: dict[str, int] = {s: 0 for s in all_statuses}
    for qid in queue_ids:
        q_stats = per_queue[qid]
        q_total = sum(q_stats.values())
        for s in all_statuses:
            totals[s] += q_stats[s]
        queues_out.append({
            "queue_id": qid,
            "queue_name": queue_names[qid],
            **q_stats,
            "total": q_total,
            "avg_duration_ms": avg_duration.get(qid),
            "completed_executions": exec_count.get(qid, 0),
        })

    # Worker counts
    worker_rows = (
        await db.execute(select(Worker.status, func.count(Worker.id)).group_by(Worker.status))
    ).all()
    worker_counts = {r[0]: r[1] for r in worker_rows}

    return ok({
        "queues": queues_out,
        "totals": {**totals, "total": sum(totals.values())},
        "workers": {
            "active": worker_counts.get("active", 0),
            "stopped": worker_counts.get("stopped", 0),
            "total": sum(worker_counts.values()),
        },
    })
