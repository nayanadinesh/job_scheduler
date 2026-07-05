import pytest

# ── helpers ──────────────────────────────────────────────────────────────────

async def _setup(client, email: str, org: str) -> tuple[str, str]:
    """Returns (token, queue_id)."""
    reg = await client.post("/api/v1/auth/register", json={
        "email": email, "password": "securepass", "org_name": org,
    })
    token = reg.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    proj = await client.post("/api/v1/projects", json={"name": "P"}, headers=headers)
    pid = proj.json()["data"]["id"]
    q = await client.post(f"/api/v1/projects/{pid}/queues", json={"name": "default"}, headers=headers)
    queue_id = q.json()["data"]["id"]
    return token, queue_id


async def _submit(client, token: str, queue_id: str, **kwargs) -> dict:
    payload = {"type": "simulate", "payload": {"durationMs": 100, "failRate": 0}, **kwargs}
    resp = await client.post(
        f"/api/v1/queues/{queue_id}/jobs",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 202, resp.json()
    return resp.json()["data"]


# ── Submit ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_submit_job_returns_queued(client):
    token, qid = await _setup(client, "j1@example.com", "J Org 1")
    job = await _submit(client, token, qid)
    assert job["status"] == "queued"
    assert job["type"] == "simulate"
    assert job["attempts"] == 0


@pytest.mark.asyncio
async def test_submit_sets_priority(client):
    token, qid = await _setup(client, "j2@example.com", "J Org 2")
    job = await _submit(client, token, qid, priority=9)
    assert job["priority"] == 9


@pytest.mark.asyncio
async def test_submit_invalid_priority_rejected(client):
    token, qid = await _setup(client, "j3@example.com", "J Org 3")
    resp = await client.post(
        f"/api/v1/queues/{qid}/jobs",
        json={"type": "simulate", "priority": 99},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


# ── Dedup ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dedup_key_prevents_duplicate_submission(client):
    token, qid = await _setup(client, "j4@example.com", "J Org 4")
    await _submit(client, token, qid, dedup_key="unique-123")
    resp = await client.post(
        f"/api/v1/queues/{qid}/jobs",
        json={"type": "simulate", "dedup_key": "unique-123"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_same_dedup_key_in_different_queues_allowed(client):
    token, qid1 = await _setup(client, "j5@example.com", "J Org 5")
    # Create a second queue in the same org
    reg = await client.post("/api/v1/auth/register", json={
        "email": "j5b@example.com", "password": "securepass", "org_name": "J Org 5b",
    })
    token2 = reg.json()["data"]["access_token"]
    proj = await client.post("/api/v1/projects", json={"name": "P2"}, headers={"Authorization": f"Bearer {token2}"})
    pid2 = proj.json()["data"]["id"]
    q2 = await client.post(f"/api/v1/projects/{pid2}/queues", json={"name": "q2"}, headers={"Authorization": f"Bearer {token2}"})
    qid2 = q2.json()["data"]["id"]

    await _submit(client, token, qid1, dedup_key="shared-key")
    # Same dedup_key in a different queue → allowed
    job2 = await _submit(client, token2, qid2, dedup_key="shared-key")
    assert job2["status"] == "queued"


# ── Read ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_get_job_by_id(client):
    token, qid = await _setup(client, "j6@example.com", "J Org 6")
    job = await _submit(client, token, qid)
    resp = await client.get(
        f"/api/v1/jobs/{job['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == job["id"]


@pytest.mark.asyncio
async def test_list_jobs_with_status_filter(client):
    token, qid = await _setup(client, "j7@example.com", "J Org 7")
    await _submit(client, token, qid)
    await _submit(client, token, qid)
    resp = await client.get(
        f"/api/v1/queues/{qid}/jobs?status=queued",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 2


@pytest.mark.asyncio
async def test_list_jobs_with_type_filter(client):
    token, qid = await _setup(client, "j8@example.com", "J Org 8")
    await _submit(client, token, qid, type="send-email")
    await _submit(client, token, qid, type="process-video")
    resp = await client.get(
        f"/api/v1/queues/{qid}/jobs?type=send-email",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["type"] == "send-email"


@pytest.mark.asyncio
async def test_executions_empty_before_worker_runs(client):
    token, qid = await _setup(client, "j9@example.com", "J Org 9")
    job = await _submit(client, token, qid)
    resp = await client.get(
        f"/api/v1/jobs/{job['id']}/executions",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"] == []


# ── Cancel ────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cancel_queued_job(client):
    token, qid = await _setup(client, "j10@example.com", "J Org 10")
    job = await _submit(client, token, qid)
    resp = await client.post(
        f"/api/v1/jobs/{job['id']}/cancel",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["status"] == "cancelled"


# ── Isolation ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_job_isolation_across_orgs(client):
    token_a, qid_a = await _setup(client, "ja@example.com", "J Org A")
    token_b, _ = await _setup(client, "jb@example.com", "J Org B")
    job = await _submit(client, token_a, qid_a)
    resp = await client.get(
        f"/api/v1/jobs/{job['id']}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code == 404
