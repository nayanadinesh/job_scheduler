import asyncio
import random
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job, JobExecution, JobLog


async def execute(db: AsyncSession, job: Job, execution: JobExecution) -> bool:
    """Simulate job execution.

    Reads durationMs and failRate from job.payload.
    Sets execution.status/finished_at/duration_ms and writes a JobLog.
    Job status transition (completed / retry / dead) is handled by apply_retry.
    Returns True on success, False on failure.
    """
    start = datetime.now(UTC)
    duration_ms: int = job.payload.get("durationMs", 100)
    fail_rate: float = job.payload.get("failRate", 0.0)

    await asyncio.sleep(duration_ms / 1000)

    now = datetime.now(UTC)
    elapsed_ms = int((now - start).total_seconds() * 1000)
    success = random.random() >= fail_rate

    execution.status = "completed" if success else "failed"
    execution.finished_at = now
    execution.duration_ms = elapsed_ms
    if not success:
        execution.error = f"Simulated failure (failRate={fail_rate})"

    db.add(
        JobLog(
            job_id=job.id,
            execution_id=execution.id,
            level="INFO" if success else "ERROR",
            message=(
                f"Job {job.type!r} {'completed' if success else 'failed'} "
                f"in {elapsed_ms}ms (attempt {job.attempts})"
            ),
        )
    )
    await db.commit()
    return success
