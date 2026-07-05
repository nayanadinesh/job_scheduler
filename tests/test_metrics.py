import pytest

from app.worker.pool import WorkerPool

# ── helpers ───────────────────────────────────────────────────────────────────

async def _setup(client, email: str, org: str) -> tuple[str, str, str]:
    reg = await client.post("/api/v1/auth/register", json={
        "email": email, "password": "securepass", "org_name": org,
    })
    token = reg.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    proj = await client.post("/api/v1/projects", json={"name": "M"}, headers=headers)
    pid = proj.json()["data"]["id"]
    q = await client.post(f"/api/v1/projects/{pid}/queues", json={"name": "metrics-q"}, headers=headers)
    return token, pid, q.json()["data"]["id"]


# ── Metrics endpoint ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_metrics_empty_org(client):
    reg = await client.post("/api/v1/auth/register", json={
        "email": "m0@example.com", "password": "securepass", "org_name": "M Org 0",
    })
    token = reg.json()["data"]["access_token"]
    resp = await client.get("/api/v1/metrics", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["queues"] == []
    assert data["totals"] == {}


@pytest.mark.asyncio
async def test_metrics_shows_queued_jobs(client):
    token, _, qid = await _setup(client, "m1@example.com", "M Org 1")
    headers = {"Authorization": f"Bearer {token}"}

    # Submit 2 jobs
    for _ in range(2):
        await client.post(f"/api/v1/queues/{qid}/jobs", json={"type": "t"}, headers=headers)

    resp = await client.get("/api/v1/metrics", headers=headers)
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["totals"]["queued"] == 2
    assert data["totals"]["total"] == 2

    queue_stat = next(q for q in data["queues"] if q["queue_id"] == qid)
    assert queue_stat["queued"] == 2
    assert queue_stat["queue_name"] == "metrics-q"


@pytest.mark.asyncio
async def test_metrics_reflects_completed_jobs(client, test_session_factory):
    token, _, qid = await _setup(client, "m2@example.com", "M Org 2")
    headers = {"Authorization": f"Bearer {token}"}

    await client.post(
        f"/api/v1/queues/{qid}/jobs",
        json={"type": "sim", "payload": {"durationMs": 5, "failRate": 0}},
        headers=headers,
    )

    pool = WorkerPool(queue_ids=[qid], session_factory=test_session_factory)
    await pool.process_batch(n=1)

    resp = await client.get("/api/v1/metrics", headers=headers)
    data = resp.json()["data"]
    assert data["totals"]["completed"] == 1
    queue_stat = next(q for q in data["queues"] if q["queue_id"] == qid)
    assert queue_stat["avg_duration_ms"] is not None
    assert queue_stat["completed_executions"] == 1


@pytest.mark.asyncio
async def test_metrics_org_isolation(client):
    token_a, _, _ = await _setup(client, "ma@example.com", "M Org A")
    token_b, _, qid_b = await _setup(client, "mb@example.com", "M Org B")

    # Submit job to org B's queue
    await client.post(
        f"/api/v1/queues/{qid_b}/jobs",
        json={"type": "b-job"},
        headers={"Authorization": f"Bearer {token_b}"},
    )

    # Org A should see no jobs
    resp_a = await client.get("/api/v1/metrics", headers={"Authorization": f"Bearer {token_a}"})
    assert resp_a.json()["data"]["totals"]["queued"] == 0


# ── Workers endpoint ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_workers_list_requires_auth(client):
    resp = await client.get("/api/v1/workers")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_workers_list_shows_registered_worker(client, test_session_factory):
    reg = await client.post("/api/v1/auth/register", json={
        "email": "wl1@example.com", "password": "securepass", "org_name": "WL Org 1",
    })
    token = reg.json()["data"]["access_token"]
    proj = (await client.post("/api/v1/projects", json={"name": "P"},
             headers={"Authorization": f"Bearer {token}"})).json()["data"]
    qid = (await client.post(f"/api/v1/projects/{proj['id']}/queues", json={"name": "q"},
             headers={"Authorization": f"Bearer {token}"})).json()["data"]["id"]

    pool = WorkerPool(queue_ids=[qid], session_factory=test_session_factory)
    await pool.start()

    resp = await client.get("/api/v1/workers", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    workers = resp.json()["data"]
    assert any(w["id"] == pool.worker_id for w in workers)
    assert any(w["status"] == "active" for w in workers)

    await pool.stop()
