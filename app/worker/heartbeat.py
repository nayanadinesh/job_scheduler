"""Worker registration and heartbeat."""
import asyncio
import socket
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy import select

from app.models.worker import Worker


async def register_worker(worker_id: str, queue_ids: list[str], session_factory: Callable) -> None:
    """Insert (or upsert) a worker row at startup."""
    async with session_factory() as db:
        existing = (await db.execute(select(Worker).where(Worker.id == worker_id))).scalar_one_or_none()
        if existing:
            existing.status = "active"
            existing.last_heartbeat_at = datetime.now(UTC)
            existing.stopped_at = None
        else:
            db.add(Worker(
                id=worker_id,
                hostname=socket.gethostname(),
                queue_ids=queue_ids,
                status="active",
            ))
        await db.commit()


async def send_heartbeat(worker_id: str, session_factory: Callable) -> None:
    """Update last_heartbeat_at for this worker."""
    async with session_factory() as db:
        result = await db.execute(select(Worker).where(Worker.id == worker_id))
        worker = result.scalar_one_or_none()
        if worker:
            worker.last_heartbeat_at = datetime.now(UTC)
            await db.commit()


async def deregister_worker(worker_id: str, session_factory: Callable) -> None:
    """Mark worker as stopped on clean shutdown."""
    async with session_factory() as db:
        result = await db.execute(select(Worker).where(Worker.id == worker_id))
        worker = result.scalar_one_or_none()
        if worker:
            worker.status = "stopped"
            worker.stopped_at = datetime.now(UTC)
            await db.commit()


async def heartbeat_loop(worker_id: str, session_factory: Callable, interval: float = 5.0) -> None:
    """Runs as an asyncio task; periodically pings the DB."""
    while True:
        await asyncio.sleep(interval)
        await send_heartbeat(worker_id, session_factory)
