"""Entry point: python -m app.worker"""
import asyncio
import logging
import sys

from sqlalchemy import select

from app.db import AsyncSessionLocal
from app.models.queue import Queue
from app.worker.pool import WorkerPool

logger = logging.getLogger(__name__)


async def main() -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(Queue.id).where(Queue.is_paused.is_(False)))
        queue_ids = [row[0] for row in result.all()]

    if not queue_ids:
        logger.warning("No active queues found. Exiting.")
        sys.exit(0)

    pool = WorkerPool(queue_ids=queue_ids, concurrency=4, poll_interval=0.5)
    await pool.start()
    logger.info("Worker %s started, polling %d queues", pool.worker_id, len(queue_ids))

    try:
        await asyncio.Event().wait()
    except (asyncio.CancelledError, KeyboardInterrupt):
        pass
    finally:
        await pool.stop()
        logger.info("Worker stopped")


if __name__ == "__main__":
    asyncio.run(main())
