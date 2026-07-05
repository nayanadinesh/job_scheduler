"""Stale-worker reaper: requeues jobs whose workers stopped heartbeating."""
import asyncio
from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from app.models.job import Job, JobLog
from app.models.worker import Worker


async def reap_once(session_factory: Callable, visibility_timeout_s: int = 30) -> int:
    """Find stale workers and requeue their running jobs.

    Returns the number of workers reaped.
    """
    cutoff = datetime.now(UTC) - timedelta(seconds=visibility_timeout_s)

    async with session_factory() as db:
        stale = (
            await db.execute(
                select(Worker).where(
                    Worker.status == "active",
                    Worker.last_heartbeat_at < cutoff,
                )
            )
        ).scalars().all()

        reaped = 0
        for worker in stale:
            running_jobs = (
                await db.execute(
                    select(Job).where(
                        Job.worker_id == worker.id,
                        Job.status.in_(["running", "claimed"]),
                    )
                )
            ).scalars().all()

            now = datetime.now(UTC)
            for job in running_jobs:
                job.status = "queued"
                job.worker_id = None
                job.claimed_at = None
                job.updated_at = now
                db.add(JobLog(
                    job_id=job.id,
                    level="WARN",
                    message=f"Requeued: worker {worker.id} missed heartbeat (timeout {visibility_timeout_s}s)",
                ))

            worker.status = "stopped"
            worker.stopped_at = now
            reaped += 1

        await db.commit()
        return reaped


async def reaper_loop(
    session_factory: Callable,
    visibility_timeout_s: int = 30,
    interval: float = 10.0,
) -> None:
    """Runs as an asyncio task; periodically reaps stale workers."""
    while True:
        await asyncio.sleep(interval)
        await reap_once(session_factory, visibility_timeout_s)
