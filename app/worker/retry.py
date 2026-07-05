"""Job retry / DLQ logic."""
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job
from app.worker.backoff import compute_delay


async def apply_retry(
    db: AsyncSession,
    job: Job,
    success: bool,
    strategy: str = "exponential",
    base_delay: float = 5.0,
    max_delay: float = 300.0,
) -> None:
    """Transition job to its post-execution state.

    - success → completed
    - failure + attempts < max_attempts → queued (rescheduled with backoff)
    - failure + attempts >= max_attempts → dead (DLQ)
    """
    now = datetime.now(UTC)

    if success:
        job.status = "completed"
    elif job.attempts >= job.max_attempts:
        job.status = "dead"
    else:
        delay = compute_delay(strategy, base_delay, max_delay, job.attempts)
        job.status = "queued"
        job.run_at = now + timedelta(seconds=delay)

    job.updated_at = now
    await db.commit()
