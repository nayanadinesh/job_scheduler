"""Scheduler: promotes delayed jobs and fires cron templates."""
import asyncio
import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from croniter import croniter
from sqlalchemy import select

from app.models.job import Job
from app.models.scheduled_job import ScheduledJob


async def tick_once(session_factory: Callable) -> tuple[int, int]:
    """Run one scheduling cycle.

    Returns (promoted_count, fired_count).
    """
    now = datetime.now(UTC)
    async with session_factory() as db:
        # 1. Promote scheduled → queued (run_at has passed)
        scheduled = (
            await db.execute(
                select(Job).where(Job.status == "scheduled", Job.run_at <= now)
            )
        ).scalars().all()
        for job in scheduled:
            job.status = "queued"
            job.updated_at = now
        promoted = len(scheduled)

        # 2. Fire cron templates whose next_run_at has passed
        due_crons = (
            await db.execute(
                select(ScheduledJob).where(
                    ScheduledJob.is_active.is_(True),
                    ScheduledJob.next_run_at <= now,
                )
            )
        ).scalars().all()

        fired = 0
        for sj in due_crons:
            db.add(Job(
                id=str(uuid.uuid4()),
                queue_id=sj.queue_id,
                type=sj.job_type,
                payload=sj.job_payload,
                status="queued",
                run_at=now,
            ))
            sj.last_fired_at = now
            sj.next_run_at = croniter(sj.cron_expr, now).get_next(datetime)
            fired += 1

        await db.commit()
        return promoted, fired


async def scheduler_loop(session_factory: Callable, interval: float = 1.0) -> None:
    """Runs as an asyncio task; periodically calls tick_once."""
    while True:
        await asyncio.sleep(interval)
        await tick_once(session_factory)
