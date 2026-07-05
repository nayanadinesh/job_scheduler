import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import engine
from app.models.job import Job, JobExecution


async def claim_one(
    db: AsyncSession,
    queue_id: str,
    worker_id: str,
) -> tuple[Job, JobExecution] | None:
    """Atomically claim the next available job.

    Uses FOR UPDATE SKIP LOCKED on Postgres so multiple workers never race
    for the same row.  Falls back to a plain SELECT on SQLite (test env).
    """
    use_skip_locked = engine.dialect.name == "postgresql"

    stmt = (
        select(Job)
        .where(
            Job.queue_id == queue_id,
            Job.status == "queued",
            Job.run_at <= datetime.now(UTC),
        )
        .order_by(Job.priority.desc(), Job.run_at.asc())
        .limit(1)
    )
    if use_skip_locked:
        stmt = stmt.with_for_update(skip_locked=True)

    result = await db.execute(stmt)
    job = result.scalar_one_or_none()
    if job is None:
        return None

    now = datetime.now(UTC)
    job.status = "running"
    job.worker_id = worker_id
    job.claimed_at = now
    job.updated_at = now
    job.attempts = (job.attempts or 0) + 1

    execution = JobExecution(
        id=str(uuid.uuid4()),
        job_id=job.id,
        attempt_no=job.attempts,
        worker_id=worker_id,
        status="running",
        started_at=now,
    )
    db.add(execution)

    await db.commit()
    await db.refresh(job)
    await db.refresh(execution)

    return job, execution
