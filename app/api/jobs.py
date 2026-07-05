from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func as sqlfunc
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.errors import ConflictError, NotFoundError
from app.core.response import accepted, created, ok
from app.db import get_db
from app.models.auth import Project, User
from app.models.job import Job, JobExecution, JobLog
from app.models.queue import Queue
from app.models.scheduled_job import ScheduledJob
from app.schemas.job import (
    ExecutionOut,
    JobCreate,
    JobOut,
    LogOut,
    ScheduledJobCreate,
    ScheduledJobOut,
)

router = APIRouter(tags=["jobs"])


async def _get_queue_for_user(queue_id: str, org_id: str, db: AsyncSession) -> Queue:
    result = await db.execute(
        select(Queue)
        .join(Project, Queue.project_id == Project.id)
        .where(Queue.id == queue_id, Project.org_id == org_id)
    )
    queue = result.scalar_one_or_none()
    if not queue:
        raise NotFoundError("Queue")
    return queue


async def _get_job_for_user(job_id: str, org_id: str, db: AsyncSession) -> Job:
    result = await db.execute(
        select(Job)
        .join(Queue, Job.queue_id == Queue.id)
        .join(Project, Queue.project_id == Project.id)
        .where(Job.id == job_id, Project.org_id == org_id)
    )
    job = result.scalar_one_or_none()
    if not job:
        raise NotFoundError("Job")
    return job


@router.post("/api/v1/queues/{queue_id}/jobs", status_code=202)
async def submit_job(
    queue_id: str,
    body: JobCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    queue = await _get_queue_for_user(queue_id, current_user.org_id, db)

    # Inherit max_attempts from queue's retry policy if set
    max_attempts = 3
    if queue.retry_policy_id:
        from app.models.queue import RetryPolicy
        rp = (await db.execute(select(RetryPolicy).where(RetryPolicy.id == queue.retry_policy_id))).scalar_one()
        max_attempts = rp.max_attempts

    now = datetime.now(UTC)
    sched = body.schedule

    def _new_job(run_at: datetime, status: str, dedup_key: str | None) -> Job:
        return Job(
            queue_id=queue_id,
            type=body.type,
            payload=body.payload,
            priority=body.priority,
            dedup_key=dedup_key,
            max_attempts=max_attempts,
            status=status,
            run_at=run_at,
        )

    # ── Batch: fan out N identical jobs ──────────────────────────────────
    if sched.kind == "batch":
        run_at = now + timedelta(seconds=sched.delay_s) if sched.delay_s else now
        status = "scheduled" if sched.delay_s else "queued"
        # A dedup_key is suffixed per-index so batch members stay unique.
        jobs = [
            _new_job(run_at, status, f"{body.dedup_key}-{i}" if body.dedup_key else None)
            for i in range(sched.count)
        ]
        db.add_all(jobs)
        await db.commit()
        for j in jobs:
            await db.refresh(j)
        return accepted([JobOut.model_validate(j).model_dump(mode="json") for j in jobs])

    # ── Single job: idempotency check via dedup_key ──────────────────────
    if body.dedup_key:
        existing = await db.execute(
            select(Job).where(Job.queue_id == queue_id, Job.dedup_key == body.dedup_key)
        )
        if existing.scalar_one_or_none():
            raise ConflictError(f"Job with dedup_key '{body.dedup_key}' already exists in this queue")

    # ── Resolve run_at + status from the schedule kind ───────────────────
    if sched.kind == "delay":
        run_at = now + timedelta(seconds=sched.delay_s)
        status = "scheduled"
    elif sched.kind == "scheduled":
        run_at = sched.run_at
        status = "queued" if sched.run_at <= now else "scheduled"
    else:  # immediate
        run_at = now
        status = "queued"

    job = _new_job(run_at, status, body.dedup_key)
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return accepted(JobOut.model_validate(job).model_dump(mode="json"))


@router.get("/api/v1/queues/{queue_id}/jobs")
async def list_jobs(
    queue_id: str,
    status: str | None = Query(None),
    type: str | None = Query(None),
    limit: int = Query(50, le=200),
    cursor: str | None = Query(None),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_queue_for_user(queue_id, current_user.org_id, db)

    stmt = select(Job).where(Job.queue_id == queue_id)
    if status:
        stmt = stmt.where(Job.status == status)
    if type:
        stmt = stmt.where(Job.type == type)
    if cursor:
        stmt = stmt.where(Job.id > cursor)
    stmt = stmt.order_by(Job.created_at.desc()).limit(limit)

    result = await db.execute(stmt)
    jobs = result.scalars().all()
    next_cursor = jobs[-1].id if len(jobs) == limit else None
    return ok(
        [JobOut.model_validate(j).model_dump(mode="json") for j in jobs],
        meta={"next_cursor": next_cursor, "limit": limit},
    )


@router.get("/api/v1/jobs/{job_id}")
async def get_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await _get_job_for_user(job_id, current_user.org_id, db)
    return ok(JobOut.model_validate(job).model_dump(mode="json"))


@router.get("/api/v1/jobs/{job_id}/executions")
async def list_executions(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_job_for_user(job_id, current_user.org_id, db)
    result = await db.execute(
        select(JobExecution)
        .where(JobExecution.job_id == job_id)
        .order_by(JobExecution.attempt_no)
    )
    execs = result.scalars().all()
    return ok([ExecutionOut.model_validate(e).model_dump(mode="json") for e in execs])


@router.get("/api/v1/jobs/{job_id}/logs")
async def list_logs(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_job_for_user(job_id, current_user.org_id, db)
    result = await db.execute(
        select(JobLog)
        .where(JobLog.job_id == job_id)
        .order_by(JobLog.ts)
    )
    logs = result.scalars().all()
    return ok([LogOut.model_validate(lg).model_dump(mode="json") for lg in logs])


@router.post("/api/v1/jobs/{job_id}/cancel")
async def cancel_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    job = await _get_job_for_user(job_id, current_user.org_id, db)
    if job.status not in ("queued", "scheduled"):
        from app.core.errors import AppError
        raise AppError("INVALID_STATE", f"Cannot cancel a job in '{job.status}' state", 409)
    job.status = "cancelled"
    await db.commit()
    return ok({"id": job.id, "status": "cancelled"})


@router.get("/api/v1/queues/{queue_id}/stats")
async def queue_stats(
    queue_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_queue_for_user(queue_id, current_user.org_id, db)
    result = await db.execute(
        select(Job.status, sqlfunc.count(Job.id))
        .where(Job.queue_id == queue_id)
        .group_by(Job.status)
    )
    counts = {row[0]: row[1] for row in result.all()}
    all_statuses = ("queued", "running", "claimed", "completed", "failed", "dead", "cancelled")
    return ok({s: counts.get(s, 0) for s in all_statuses} | {"total": sum(counts.values())})


@router.post("/api/v1/jobs/{job_id}/retry")
async def retry_dead_job(
    job_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Requeue a dead job for a fresh run (resets attempt counter)."""
    job = await _get_job_for_user(job_id, current_user.org_id, db)
    if job.status != "dead":
        from app.core.errors import AppError
        raise AppError("INVALID_STATE", f"Only dead jobs can be retried, got '{job.status}'", 409)
    now = datetime.now(UTC)
    job.status = "queued"
    job.attempts = 0
    job.run_at = now
    job.updated_at = now
    await db.commit()
    return ok({"id": job.id, "status": "queued"})


# ── Cron / ScheduledJobs ──────────────────────────────────────────────────────

@router.post("/api/v1/queues/{queue_id}/scheduled-jobs", status_code=201)
async def create_scheduled_job(
    queue_id: str,
    body: ScheduledJobCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_queue_for_user(queue_id, current_user.org_id, db)
    from croniter import croniter
    next_run = croniter(body.cron_expr, datetime.now(UTC)).get_next(datetime)
    sj = ScheduledJob(
        queue_id=queue_id,
        name=body.name,
        cron_expr=body.cron_expr,
        job_type=body.job_type,
        job_payload=body.job_payload,
        description=body.description,
        next_run_at=next_run,
    )
    db.add(sj)
    await db.commit()
    await db.refresh(sj)
    return created(ScheduledJobOut.model_validate(sj).model_dump(mode="json"))


@router.get("/api/v1/queues/{queue_id}/scheduled-jobs")
async def list_scheduled_jobs(
    queue_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await _get_queue_for_user(queue_id, current_user.org_id, db)
    result = await db.execute(
        select(ScheduledJob).where(ScheduledJob.queue_id == queue_id).order_by(ScheduledJob.created_at)
    )
    jobs = result.scalars().all()
    return ok([ScheduledJobOut.model_validate(sj).model_dump(mode="json") for sj in jobs])


@router.delete("/api/v1/scheduled-jobs/{sj_id}", status_code=204)
async def delete_scheduled_job(
    sj_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ScheduledJob)
        .join(Queue, ScheduledJob.queue_id == Queue.id)
        .join(Project, Queue.project_id == Project.id)
        .where(ScheduledJob.id == sj_id, Project.org_id == current_user.org_id)
    )
    sj = result.scalar_one_or_none()
    if not sj:
        raise NotFoundError("ScheduledJob")
    await db.delete(sj)
    await db.commit()
