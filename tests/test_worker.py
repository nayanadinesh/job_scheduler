import pytest

from app.worker.pool import WorkerPool

# ── helpers ───────────────────────────────────────────────────────────────────

async def _setup(client, email: str, org: str) -> tuple[str, str]:
    reg = await client.post("/api/v1/auth/register", json={
        "email": email, "password": "securepass", "org_name": org,
    })
    token = reg.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    proj = await client.post("/api/v1/projects", json={"name": "WP"}, headers=headers)
    pid = proj.json()["data"]["id"]
    q = await client.post(f"/api/v1/projects/{pid}/queues", json={"name": "jobs"}, headers=headers)
    return token, q.json()["data"]["id"]


async def _submit(client, token: str, qid: str, *, duration_ms: int = 10, fail_rate: float = 0.0) -> dict:
    resp = await client.post(
        f"/api/v1/queues/{qid}/jobs",
        json={"type": "simulate", "payload": {"durationMs": duration_ms, "failRate": fail_rate}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 202
    return resp.json()["data"]


# ── basic execution ───────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_worker_processes_job_to_completed(client, test_session_factory):
    token, qid = await _setup(client, "w1@example.com", "W Org 1")
    job = await _submit(client, token, qid, duration_ms=10, fail_rate=0.0)

    pool = WorkerPool(queue_ids=[qid], session_factory=test_session_factory)
    processed = await pool.process_batch(n=1)

    assert processed == 1
    resp = await client.get(f"/api/v1/jobs/{job['id']}", headers={"Authorization": f"Bearer {token}"})
    assert resp.json()["data"]["status"] == "completed"
    assert resp.json()["data"]["attempts"] == 1


@pytest.mark.asyncio
async def test_worker_processes_multiple_jobs(client, test_session_factory):
    token, qid = await _setup(client, "w2@example.com", "W Org 2")
    for _ in range(3):
        await _submit(client, token, qid, duration_ms=5)

    pool = WorkerPool(queue_ids=[qid], session_factory=test_session_factory)
    processed = await pool.process_batch(n=5)

    assert processed == 3


@pytest.mark.asyncio
async def test_worker_forced_failure(client, test_session_factory):
    token, qid = await _setup(client, "w3@example.com", "W Org 3")
    job = await _submit(client, token, qid, duration_ms=5, fail_rate=1.0)

    pool = WorkerPool(queue_ids=[qid], session_factory=test_session_factory)
    await pool.process_batch(n=1)

    resp = await client.get(f"/api/v1/jobs/{job['id']}", headers={"Authorization": f"Bearer {token}"})
    data = resp.json()["data"]
    # Default max_attempts=3: first failure reschedules the job for retry
    assert data["status"] == "queued"
    assert data["attempts"] == 1


@pytest.mark.asyncio
async def test_worker_creates_execution_record(client, test_session_factory):
    token, qid = await _setup(client, "w4@example.com", "W Org 4")
    job = await _submit(client, token, qid, duration_ms=5)

    pool = WorkerPool(queue_ids=[qid], session_factory=test_session_factory)
    await pool.process_batch(n=1)

    executions = (
        await client.get(f"/api/v1/jobs/{job['id']}/executions", headers={"Authorization": f"Bearer {token}"})
    ).json()["data"]
    assert len(executions) == 1
    assert executions[0]["status"] == "completed"
    assert executions[0]["duration_ms"] is not None


@pytest.mark.asyncio
async def test_worker_creates_log_entry(client, test_session_factory):
    token, qid = await _setup(client, "w5@example.com", "W Org 5")
    job = await _submit(client, token, qid, duration_ms=5)

    pool = WorkerPool(queue_ids=[qid], session_factory=test_session_factory)
    await pool.process_batch(n=1)

    logs = (
        await client.get(f"/api/v1/jobs/{job['id']}/logs", headers={"Authorization": f"Bearer {token}"})
    ).json()["data"]
    assert len(logs) >= 1
    assert logs[0]["level"] == "INFO"


@pytest.mark.asyncio
async def test_process_batch_returns_zero_when_queue_empty(client, test_session_factory):
    token, qid = await _setup(client, "w6@example.com", "W Org 6")
    pool = WorkerPool(queue_ids=[qid], session_factory=test_session_factory)
    processed = await pool.process_batch(n=5)
    assert processed == 0


# ── stats endpoint ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_queue_stats_reflect_execution(client, test_session_factory):
    token, qid = await _setup(client, "w7@example.com", "W Org 7")
    await _submit(client, token, qid, duration_ms=5)

    headers = {"Authorization": f"Bearer {token}"}

    stats_before = (await client.get(f"/api/v1/queues/{qid}/stats", headers=headers)).json()["data"]
    assert stats_before["queued"] == 1

    pool = WorkerPool(queue_ids=[qid], session_factory=test_session_factory)
    await pool.process_batch(n=1)

    stats_after = (await client.get(f"/api/v1/queues/{qid}/stats", headers=headers)).json()["data"]
    assert stats_after["queued"] == 0
    assert stats_after["completed"] == 1
    assert stats_after["total"] == 1


@pytest.mark.asyncio
async def test_queue_stats_empty_queue(client):
    token, qid = await _setup(client, "w8@example.com", "W Org 8")
    headers = {"Authorization": f"Bearer {token}"}
    stats = (await client.get(f"/api/v1/queues/{qid}/stats", headers=headers)).json()["data"]
    assert stats["total"] == 0
    assert stats["queued"] == 0
