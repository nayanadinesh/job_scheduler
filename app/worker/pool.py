import asyncio
import contextlib
import uuid
from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.models.queue import Queue
from app.scheduler.reaper import reaper_loop
from app.worker.claimer import claim_one
from app.worker.executor import execute
from app.worker.heartbeat import deregister_worker, heartbeat_loop, register_worker
from app.worker.retry import apply_retry


class WorkerPool:
    """Async worker pool: polls queues and executes jobs concurrently.

    Pass a custom ``session_factory`` in tests so the pool uses the test DB
    instead of the production engine.
    """

    def __init__(
        self,
        queue_ids: list[str],
        concurrency: int = 4,
        poll_interval: float = 0.5,
        heartbeat_interval: float = 5.0,
        reaper_interval: float = 10.0,
        visibility_timeout_s: int = 30,
        session_factory: Callable | None = None,
    ) -> None:
        self.queue_ids = queue_ids
        self.concurrency = concurrency
        self.poll_interval = poll_interval
        self.heartbeat_interval = heartbeat_interval
        self.reaper_interval = reaper_interval
        self.visibility_timeout_s = visibility_timeout_s
        self.worker_id = str(uuid.uuid4())
        self._session_factory = session_factory
        self._running = False
        self._semaphore: asyncio.Semaphore | None = None
        self._tasks: list[asyncio.Task] = []

    def _make_session(self):
        if self._session_factory is not None:
            return self._session_factory()
        from app.db import AsyncSessionLocal
        return AsyncSessionLocal()

    async def _load_retry_config(self, queue_id: str) -> tuple[str, float, float]:
        async with self._make_session() as db:
            result = await db.execute(
                select(Queue).where(Queue.id == queue_id).options(selectinload(Queue.retry_policy))
            )
            q = result.scalar_one_or_none()
            if q and q.retry_policy:
                rp = q.retry_policy
                return rp.strategy, float(rp.base_delay_s), float(rp.max_delay_s)
        return "exponential", 5.0, 300.0

    async def process_one(self, queue_id: str) -> bool:
        """Claim and execute one job. Returns True if a job was processed."""
        strategy, base_delay, max_delay = await self._load_retry_config(queue_id)

        async with self._make_session() as db:
            result = await claim_one(db, queue_id, self.worker_id)
            if result is None:
                return False
            job, execution = result
            success = await execute(db, job, execution)
            await db.refresh(job)
            await apply_retry(db, job, success, strategy, base_delay, max_delay)

        return True

    async def process_batch(self, n: int = 10) -> int:
        """Process up to n jobs across all queues. Returns count processed."""
        processed = 0
        for queue_id in self.queue_ids:
            for _ in range(n):
                if not await self.process_one(queue_id):
                    break
                processed += 1
        return processed

    async def _run_with_semaphore(self, queue_id: str) -> None:
        assert self._semaphore is not None
        async with self._semaphore:
            await self.process_one(queue_id)

    async def _poll_loop(self) -> None:
        while self._running:
            for queue_id in self.queue_ids:
                asyncio.create_task(self._run_with_semaphore(queue_id))
            await asyncio.sleep(self.poll_interval)

    async def start(self) -> None:
        self._running = True
        self._semaphore = asyncio.Semaphore(self.concurrency)

        await register_worker(self.worker_id, self.queue_ids, self._make_session)

        self._tasks = [
            asyncio.create_task(self._poll_loop()),
            asyncio.create_task(
                heartbeat_loop(self.worker_id, self._make_session, self.heartbeat_interval)
            ),
            asyncio.create_task(
                reaper_loop(self._make_session, self.visibility_timeout_s, self.reaper_interval)
            ),
        ]

    async def stop(self) -> None:
        self._running = False
        for task in self._tasks:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self._tasks.clear()
        await deregister_worker(self.worker_id, self._make_session)
