from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models.job import Job, JobLog
from app.models.worker import Worker
from app.scheduler.reaper import reap_once
from app.worker.heartbeat import deregister_worker, register_worker, send_heartbeat
from app.worker.pool import WorkerPool

# ── helpers ───────────────────────────────────────────────────────────────────

async def _setup(client, email: str, org: str) -> tuple[str, str]:
    reg = await client.post("/api/v1/auth/register", json={
        "email": email, "password": "securepass", "org_name": org,
    })
    token = reg.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    proj = await client.post("/api/v1/projects", json={"name": "HR"}, headers=headers)
    pid = proj.json()["data"]["id"]
    q = await client.post(f"/api/v1/projects/{pid}/queues", json={"name": "q"}, headers=headers)
    return token, q.json()["data"]["id"]


# ── Worker registration ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_register_creates_worker_row(test_session_factory):
    wid = "test-worker-reg"
    await register_worker(wid, ["q1"], test_session_factory)

    async with test_session_factory() as db:
        w = (await db.execute(select(Worker).where(Worker.id == wid))).scalar_one()
    assert w.status == "active"
    assert w.queue_ids == ["q1"]


@pytest.mark.asyncio
async def test_deregister_marks_worker_stopped(test_session_factory):
    wid = "test-worker-dereg"
    await register_worker(wid, [], test_session_factory)
    await deregister_worker(wid, test_session_factory)

    async with test_session_factory() as db:
        w = (await db.execute(select(Worker).where(Worker.id == wid))).scalar_one()
    assert w.status == "stopped"
    assert w.stopped_at is not None


@pytest.mark.asyncio
async def test_re_register_existing_worker_upserts(test_session_factory):
    wid = "test-worker-rereg"
    await register_worker(wid, ["q1"], test_session_factory)
    await deregister_worker(wid, test_session_factory)

    # Re-registering reactivates the same row
    await register_worker(wid, ["q1", "q2"], test_session_factory)

    async with test_session_factory() as db:
        w = (await db.execute(select(Worker).where(Worker.id == wid))).scalar_one()
    assert w.status == "active"
    assert w.stopped_at is None


# ── Heartbeat ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_heartbeat_updates_timestamp(test_session_factory):
    wid = "test-worker-hb"
    await register_worker(wid, [], test_session_factory)

    # Set a clearly old timestamp (year 2000) to avoid tz-comparison edge cases
    async with test_session_factory() as db:
        w = (await db.execute(select(Worker).where(Worker.id == wid))).scalar_one()
        w.last_heartbeat_at = datetime(2000, 1, 1, tzinfo=UTC)
        await db.commit()

    await send_heartbeat(wid, test_session_factory)

    async with test_session_factory() as db:
        w2 = (await db.execute(select(Worker).where(Worker.id == wid))).scalar_one()

    # Strip tz for SQLite compat, then verify it's recent (not year 2000)
    ts = w2.last_heartbeat_at
    if ts.tzinfo:
        ts = ts.replace(tzinfo=None)
    assert ts.year >= 2026


# ── Reaper ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_reaper_requeues_running_jobs_for_stale_worker(client, test_session_factory):
    token, qid = await _setup(client, "hr1@example.com", "HR Org 1")

    # Submit and start processing (creates running job)
    resp = await client.post(
        f"/api/v1/queues/{qid}/jobs",
        json={"type": "sim", "payload": {"durationMs": 5, "failRate": 0}},
        headers={"Authorization": f"Bearer {token}"},
    )
    job_id = resp.json()["data"]["id"]

    # Manually create a stale worker row and set job to running
    stale_wid = "stale-worker-001"
    async with test_session_factory() as db:
        db.add(Worker(
            id=stale_wid,
            hostname="dead-host",
            queue_ids=[qid],
            status="active",
            last_heartbeat_at=datetime.now(UTC) - timedelta(seconds=120),
        ))
        job = (await db.execute(select(Job).where(Job.id == job_id))).scalar_one()
        job.status = "running"
        job.worker_id = stale_wid
        await db.commit()

    # Run reaper with 30s timeout
    reaped = await reap_once(test_session_factory, visibility_timeout_s=30)
    assert reaped == 1

    # Job should be requeued
    async with test_session_factory() as db:
        job = (await db.execute(select(Job).where(Job.id == job_id))).scalar_one()
    assert job.status == "queued"
    assert job.worker_id is None


@pytest.mark.asyncio
async def test_reaper_leaves_fresh_workers_alone(test_session_factory, client):
    token, qid = await _setup(client, "hr2@example.com", "HR Org 2")

    resp = await client.post(
        f"/api/v1/queues/{qid}/jobs",
        json={"type": "sim", "payload": {"durationMs": 5, "failRate": 0}},
        headers={"Authorization": f"Bearer {token}"},
    )
    job_id = resp.json()["data"]["id"]

    fresh_wid = "fresh-worker-001"
    async with test_session_factory() as db:
        db.add(Worker(
            id=fresh_wid,
            hostname="live-host",
            queue_ids=[qid],
            status="active",
            last_heartbeat_at=datetime.now(UTC),  # fresh!
        ))
        job = (await db.execute(select(Job).where(Job.id == job_id))).scalar_one()
        job.status = "running"
        job.worker_id = fresh_wid
        await db.commit()

    reaped = await reap_once(test_session_factory, visibility_timeout_s=30)
    assert reaped == 0

    async with test_session_factory() as db:
        job = (await db.execute(select(Job).where(Job.id == job_id))).scalar_one()
    assert job.status == "running"


@pytest.mark.asyncio
async def test_reaper_writes_log_for_reaped_jobs(test_session_factory, client):
    token, qid = await _setup(client, "hr3@example.com", "HR Org 3")

    resp = await client.post(
        f"/api/v1/queues/{qid}/jobs",
        json={"type": "sim", "payload": {}},
        headers={"Authorization": f"Bearer {token}"},
    )
    job_id = resp.json()["data"]["id"]

    stale_wid = "stale-worker-log"
    async with test_session_factory() as db:
        db.add(Worker(
            id=stale_wid, hostname="x", queue_ids=[],
            status="active",
            last_heartbeat_at=datetime.now(UTC) - timedelta(seconds=60),
        ))
        job = (await db.execute(select(Job).where(Job.id == job_id))).scalar_one()
        job.status = "running"
        job.worker_id = stale_wid
        await db.commit()

    await reap_once(test_session_factory, visibility_timeout_s=30)

    async with test_session_factory() as db:
        logs = (await db.execute(select(JobLog).where(JobLog.job_id == job_id))).scalars().all()
    assert len(logs) >= 1
    assert any("Requeued" in lg.message for lg in logs)


# ── Pool integration: worker registers on start ───────────────────────────────

@pytest.mark.asyncio
async def test_pool_registers_worker_on_start(test_session_factory, client):
    _, qid = await _setup(client, "hr4@example.com", "HR Org 4")
    pool = WorkerPool(queue_ids=[qid], session_factory=test_session_factory)
    await pool.start()

    async with test_session_factory() as db:
        w = (await db.execute(select(Worker).where(Worker.id == pool.worker_id))).scalar_one()
    assert w.status == "active"

    await pool.stop()

    async with test_session_factory() as db:
        w2 = (await db.execute(select(Worker).where(Worker.id == pool.worker_id))).scalar_one()
    assert w2.status == "stopped"
