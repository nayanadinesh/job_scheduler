"""Worker status API."""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.response import ok
from app.db import get_db
from app.models.auth import User
from app.models.worker import Worker

router = APIRouter(tags=["workers"])


@router.get("/api/v1/workers")
async def list_workers(
    _: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List all workers (system-wide; requires auth)."""
    result = await db.execute(select(Worker).order_by(Worker.started_at.desc()))
    workers = result.scalars().all()
    return ok([
        {
            "id": w.id,
            "hostname": w.hostname,
            "queue_ids": w.queue_ids,
            "status": w.status,
            "last_heartbeat_at": w.last_heartbeat_at.isoformat() if w.last_heartbeat_at else None,
            "started_at": w.started_at.isoformat() if w.started_at else None,
            "stopped_at": w.stopped_at.isoformat() if w.stopped_at else None,
        }
        for w in workers
    ])
