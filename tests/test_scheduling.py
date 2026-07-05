from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from app.models.job import Job
from app.models.scheduled_job import ScheduledJob
from app.scheduler.scheduler import tick_once

# ── helpers ───────────────────────────────────────────────────────────────────

async def _setup(client, email: str, org: str) -> tuple[str, str]:
    reg = await client.post("/api/v1/auth/register", json={
        "email": email, "password": "securepass", "org_name": org,
    })
    token = reg.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    proj = await client.post("/api/v1/projects", json={"name": "S"}, headers=headers)
    pid = proj.json()["data"]["id"]
    q = await client.post(f"/api/v1/projects/{pid}/queues", json={"name": "sched"}, headers=headers)
    return token, q.json()["data"]["id"]


# ── Delayed jobs ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_delayed_job_starts_in_scheduled_state(client):
    token, qid = await _setup(client, "sc1@example.com", "SC Org 1")
    resp = await client.post(
        f"/api/v1/queues/{qid}/jobs",
        json={"type": "later", "schedule": {"kind": "delay", "delay_s": 60}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 202
    data = resp.json()["data"]
    assert data["status"] == "scheduled"


@pytest.mark.asyncio
async def test_immediate_job_starts_in_queued_state(client):
    token, qid = await _setup(client, "sc2@example.com", "SC Org 2")
    resp = await client.post(
        f"/api/v1/queues/{qid}/jobs",
        json={"type": "now", "schedule": {"kind": "immediate"}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 202
    assert resp.json()["data"]["status"] == "queued"


@pytest.mark.asyncio
async def test_scheduler_promotes_due_delayed_jobs(client, test_session_factory):
    token, qid = await _setup(client, "sc3@example.com", "SC Org 3")

    # Submit a delayed job, then backdating run_at to simulate time passing
    resp = await client.post(
        f"/api/v1/queues/{qid}/jobs",
        json={"type": "due", "schedule": {"kind": "delay", "delay_s": 3600}},
        headers={"Authorization": f"Bearer {token}"},
    )
    job_id = resp.json()["data"]["id"]

    # Manually backdate run_at so the job is "due"
    async with test_session_factory() as db:
        job = (await db.execute(select(Job).where(Job.id == job_id))).scalar_one()
        job.run_at = datetime.now(UTC) - timedelta(seconds=1)
        await db.commit()

    promoted, fired = await tick_once(test_session_factory)
    assert promoted >= 1

    async with test_session_factory() as db:
        job = (await db.execute(select(Job).where(Job.id == job_id))).scalar_one()
    assert job.status == "queued"


@pytest.mark.asyncio
async def test_scheduler_does_not_promote_future_delayed_jobs(client, test_session_factory):
    token, qid = await _setup(client, "sc4@example.com", "SC Org 4")
    resp = await client.post(
        f"/api/v1/queues/{qid}/jobs",
        json={"type": "future", "schedule": {"kind": "delay", "delay_s": 3600}},
        headers={"Authorization": f"Bearer {token}"},
    )
    job_id = resp.json()["data"]["id"]

    promoted, _ = await tick_once(test_session_factory)

    async with test_session_factory() as db:
        job = (await db.execute(select(Job).where(Job.id == job_id))).scalar_one()
    assert job.status == "scheduled"  # not promoted yet


# ── Scheduled (absolute timestamp) jobs ───────────────────────────────────────

@pytest.mark.asyncio
async def test_scheduled_future_timestamp_is_scheduled(client):
    token, qid = await _setup(client, "sat1@example.com", "SAT Org 1")
    future = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    resp = await client.post(
        f"/api/v1/queues/{qid}/jobs",
        json={"type": "at", "schedule": {"kind": "scheduled", "run_at": future}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 202
    assert resp.json()["data"]["status"] == "scheduled"


@pytest.mark.asyncio
async def test_scheduled_past_timestamp_is_queued(client):
    token, qid = await _setup(client, "sat2@example.com", "SAT Org 2")
    past = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
    resp = await client.post(
        f"/api/v1/queues/{qid}/jobs",
        json={"type": "at", "schedule": {"kind": "scheduled", "run_at": past}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 202
    assert resp.json()["data"]["status"] == "queued"


@pytest.mark.asyncio
async def test_scheduler_promotes_due_scheduled_job(client, test_session_factory):
    token, qid = await _setup(client, "sat3@example.com", "SAT Org 3")
    future = (datetime.now(UTC) + timedelta(hours=2)).isoformat()
    resp = await client.post(
        f"/api/v1/queues/{qid}/jobs",
        json={"type": "at-due", "schedule": {"kind": "scheduled", "run_at": future}},
        headers={"Authorization": f"Bearer {token}"},
    )
    job_id = resp.json()["data"]["id"]

    async with test_session_factory() as db:
        job = (await db.execute(select(Job).where(Job.id == job_id))).scalar_one()
        job.run_at = datetime.now(UTC) - timedelta(seconds=1)
        await db.commit()

    promoted, _ = await tick_once(test_session_factory)
    assert promoted >= 1

    async with test_session_factory() as db:
        job = (await db.execute(select(Job).where(Job.id == job_id))).scalar_one()
    assert job.status == "queued"


# ── Batch fan-out ─────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_batch_fans_out_jobs(client, test_session_factory):
    token, qid = await _setup(client, "bat1@example.com", "BAT Org 1")
    resp = await client.post(
        f"/api/v1/queues/{qid}/jobs",
        json={"type": "fanned", "schedule": {"kind": "batch", "count": 5}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 202
    data = resp.json()["data"]
    assert isinstance(data, list)
    assert len(data) == 5
    assert all(j["status"] == "queued" for j in data)

    async with test_session_factory() as db:
        jobs = (await db.execute(select(Job).where(Job.queue_id == qid, Job.type == "fanned"))).scalars().all()
    assert len(jobs) == 5


@pytest.mark.asyncio
async def test_batch_with_delay_is_scheduled(client):
    token, qid = await _setup(client, "bat2@example.com", "BAT Org 2")
    resp = await client.post(
        f"/api/v1/queues/{qid}/jobs",
        json={"type": "fanned-delay", "schedule": {"kind": "batch", "count": 3, "delay_s": 60}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 202
    data = resp.json()["data"]
    assert len(data) == 3
    assert all(j["status"] == "scheduled" for j in data)


@pytest.mark.asyncio
async def test_batch_dedup_keys_are_suffixed(client, test_session_factory):
    token, qid = await _setup(client, "bat3@example.com", "BAT Org 3")
    resp = await client.post(
        f"/api/v1/queues/{qid}/jobs",
        json={"type": "fanned-dedup", "dedup_key": "run-42", "schedule": {"kind": "batch", "count": 3}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 202
    keys = sorted(j["dedup_key"] for j in resp.json()["data"])
    assert keys == ["run-42-0", "run-42-1", "run-42-2"]


@pytest.mark.asyncio
async def test_batch_count_below_two_rejected(client):
    token, qid = await _setup(client, "bat4@example.com", "BAT Org 4")
    resp = await client.post(
        f"/api/v1/queues/{qid}/jobs",
        json={"type": "x", "schedule": {"kind": "batch", "count": 1}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


# ── Cron scheduled jobs ───────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_scheduled_job(client):
    token, qid = await _setup(client, "sc5@example.com", "SC Org 5")
    resp = await client.post(
        f"/api/v1/queues/{qid}/scheduled-jobs",
        json={
            "name": "hourly-sync",
            "cron_expr": "0 * * * *",
            "job_type": "sync-data",
            "job_payload": {"source": "s3"},
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["cron_expr"] == "0 * * * *"
    assert data["next_run_at"] is not None


@pytest.mark.asyncio
async def test_invalid_cron_expression_rejected(client):
    token, qid = await _setup(client, "sc6@example.com", "SC Org 6")
    resp = await client.post(
        f"/api/v1/queues/{qid}/scheduled-jobs",
        json={"name": "bad", "cron_expr": "not-a-cron", "job_type": "x"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_scheduler_fires_due_cron(client, test_session_factory):
    token, qid = await _setup(client, "sc7@example.com", "SC Org 7")

    # Create a cron job with next_run_at in the past (simulate it being due)
    resp = await client.post(
        f"/api/v1/queues/{qid}/scheduled-jobs",
        json={"name": "due-cron", "cron_expr": "* * * * *", "job_type": "cron-task"},
        headers={"Authorization": f"Bearer {token}"},
    )
    sj_id = resp.json()["data"]["id"]

    # Backdate next_run_at to simulate it's overdue
    async with test_session_factory() as db:
        sj = (await db.execute(select(ScheduledJob).where(ScheduledJob.id == sj_id))).scalar_one()
        sj.next_run_at = datetime.now(UTC) - timedelta(seconds=1)
        await db.commit()

    _, fired = await tick_once(test_session_factory)
    assert fired >= 1

    # A new Job should have been created
    async with test_session_factory() as db:
        jobs = (await db.execute(select(Job).where(Job.queue_id == qid, Job.type == "cron-task"))).scalars().all()
    assert len(jobs) == 1
    assert jobs[0].status == "queued"


@pytest.mark.asyncio
async def test_list_scheduled_jobs(client):
    token, qid = await _setup(client, "sc8@example.com", "SC Org 8")
    await client.post(
        f"/api/v1/queues/{qid}/scheduled-jobs",
        json={"name": "j1", "cron_expr": "0 * * * *", "job_type": "t1"},
        headers={"Authorization": f"Bearer {token}"},
    )
    await client.post(
        f"/api/v1/queues/{qid}/scheduled-jobs",
        json={"name": "j2", "cron_expr": "0 0 * * *", "job_type": "t2"},
        headers={"Authorization": f"Bearer {token}"},
    )
    resp = await client.get(
        f"/api/v1/queues/{qid}/scheduled-jobs",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 2


@pytest.mark.asyncio
async def test_delete_scheduled_job(client):
    token, qid = await _setup(client, "sc9@example.com", "SC Org 9")
    sj = (await client.post(
        f"/api/v1/queues/{qid}/scheduled-jobs",
        json={"name": "temp", "cron_expr": "0 * * * *", "job_type": "t"},
        headers={"Authorization": f"Bearer {token}"},
    )).json()["data"]

    resp = await client.delete(
        f"/api/v1/scheduled-jobs/{sj['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204
