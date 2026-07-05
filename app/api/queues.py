from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.errors import NotFoundError
from app.core.response import created, ok
from app.db import get_db
from app.models.auth import Project, User
from app.models.queue import Queue, RetryPolicy
from app.schemas.queue import QueueCreate, QueueOut, QueueUpdate

router = APIRouter(tags=["queues"])


async def _get_queue_or_404(queue_id: str, org_id: str, db: AsyncSession) -> Queue:
    result = await db.execute(
        select(Queue)
        .join(Project, Queue.project_id == Project.id)
        .where(Queue.id == queue_id, Project.org_id == org_id)
    )
    queue = result.scalar_one_or_none()
    if not queue:
        raise NotFoundError("Queue")
    return queue


@router.get("/api/v1/projects/{project_id}/queues")
async def list_queues(
    project_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    # Verify project belongs to user's org
    proj = await db.execute(
        select(Project).where(Project.id == project_id, Project.org_id == current_user.org_id)
    )
    if not proj.scalar_one_or_none():
        raise NotFoundError("Project")

    result = await db.execute(select(Queue).where(Queue.project_id == project_id))
    queues = result.scalars().all()
    return ok([QueueOut.model_validate(q).model_dump(mode="json") for q in queues])


@router.post("/api/v1/projects/{project_id}/queues", status_code=201)
async def create_queue(
    project_id: str,
    body: QueueCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    proj = await db.execute(
        select(Project).where(Project.id == project_id, Project.org_id == current_user.org_id)
    )
    if not proj.scalar_one_or_none():
        raise NotFoundError("Project")

    retry_policy_id = None
    if body.retry_policy:
        rp = RetryPolicy(
            strategy=body.retry_policy.strategy,
            base_delay_s=body.retry_policy.base_delay_s,
            max_attempts=body.retry_policy.max_attempts,
            max_delay_s=body.retry_policy.max_delay_s,
        )
        db.add(rp)
        await db.flush()
        retry_policy_id = rp.id

    queue = Queue(
        project_id=project_id,
        name=body.name,
        priority=body.priority,
        concurrency_limit=body.concurrency_limit,
        retry_policy_id=retry_policy_id,
    )
    db.add(queue)
    await db.commit()
    await db.refresh(queue)
    # eager-load the retry_policy for serialization
    if queue.retry_policy_id:
        await db.refresh(queue, ["retry_policy"])
    return created(QueueOut.model_validate(queue).model_dump(mode="json"))


@router.get("/api/v1/queues/{queue_id}")
async def get_queue(
    queue_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    queue = await _get_queue_or_404(queue_id, current_user.org_id, db)
    if queue.retry_policy_id:
        await db.refresh(queue, ["retry_policy"])
    return ok(QueueOut.model_validate(queue).model_dump(mode="json"))


@router.patch("/api/v1/queues/{queue_id}")
async def update_queue(
    queue_id: str,
    body: QueueUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    queue = await _get_queue_or_404(queue_id, current_user.org_id, db)
    if body.name is not None:
        queue.name = body.name
    if body.priority is not None:
        queue.priority = body.priority
    if body.concurrency_limit is not None:
        queue.concurrency_limit = body.concurrency_limit
    await db.commit()
    await db.refresh(queue)
    if queue.retry_policy_id:
        await db.refresh(queue, ["retry_policy"])
    return ok(QueueOut.model_validate(queue).model_dump(mode="json"))


@router.post("/api/v1/queues/{queue_id}/pause")
async def pause_queue(
    queue_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    queue = await _get_queue_or_404(queue_id, current_user.org_id, db)
    queue.is_paused = True
    await db.commit()
    return ok({"id": queue.id, "is_paused": True})


@router.post("/api/v1/queues/{queue_id}/resume")
async def resume_queue(
    queue_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    queue = await _get_queue_or_404(queue_id, current_user.org_id, db)
    queue.is_paused = False
    await db.commit()
    return ok({"id": queue.id, "is_paused": False})


@router.delete("/api/v1/queues/{queue_id}", status_code=204)
async def delete_queue(
    queue_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    queue = await _get_queue_or_404(queue_id, current_user.org_id, db)
    await db.delete(queue)
    await db.commit()
