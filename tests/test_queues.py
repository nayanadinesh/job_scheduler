import pytest

# ── helpers ──────────────────────────────────────────────────────────────────

async def _register(client, email: str, org: str) -> tuple[str, str]:
    """Register a user and return (token, project_id)."""
    reg = await client.post("/api/v1/auth/register", json={
        "email": email, "password": "securepass", "org_name": org,
    })
    token = reg.json()["data"]["access_token"]
    proj = await client.post(
        "/api/v1/projects",
        json={"name": "Test Project"},
        headers={"Authorization": f"Bearer {token}"},
    )
    project_id = proj.json()["data"]["id"]
    return token, project_id


async def _create_queue(client, token: str, project_id: str, **kwargs) -> dict:
    payload = {"name": "default", **kwargs}
    resp = await client.post(
        f"/api/v1/projects/{project_id}/queues",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    return resp.json()["data"]


# ── CRUD ──────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_create_queue_defaults(client):
    token, pid = await _register(client, "q1@example.com", "Q Org 1")
    q = await _create_queue(client, token, pid)
    assert q["name"] == "default"
    assert q["priority"] == 5
    assert q["concurrency_limit"] == 10
    assert q["is_paused"] is False
    assert q["retry_policy"] is None


@pytest.mark.asyncio
async def test_create_queue_with_retry_policy(client):
    token, pid = await _register(client, "q2@example.com", "Q Org 2")
    q = await _create_queue(client, token, pid, retry_policy={
        "strategy": "exponential",
        "base_delay_s": 2,
        "max_attempts": 5,
        "max_delay_s": 300,
    })
    assert q["retry_policy"]["strategy"] == "exponential"
    assert q["retry_policy"]["max_attempts"] == 5


@pytest.mark.asyncio
async def test_list_queues(client):
    token, pid = await _register(client, "q3@example.com", "Q Org 3")
    await _create_queue(client, token, pid, name="q-a")
    await _create_queue(client, token, pid, name="q-b")
    resp = await client.get(
        f"/api/v1/projects/{pid}/queues",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 2


@pytest.mark.asyncio
async def test_get_queue_by_id(client):
    token, pid = await _register(client, "q4@example.com", "Q Org 4")
    q = await _create_queue(client, token, pid)
    resp = await client.get(
        f"/api/v1/queues/{q['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["id"] == q["id"]


@pytest.mark.asyncio
async def test_update_queue(client):
    token, pid = await _register(client, "q5@example.com", "Q Org 5")
    q = await _create_queue(client, token, pid)
    resp = await client.patch(
        f"/api/v1/queues/{q['id']}",
        json={"name": "renamed", "concurrency_limit": 5},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["name"] == "renamed"
    assert data["concurrency_limit"] == 5


@pytest.mark.asyncio
async def test_delete_queue(client):
    token, pid = await _register(client, "q6@example.com", "Q Org 6")
    q = await _create_queue(client, token, pid)
    resp = await client.delete(
        f"/api/v1/queues/{q['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 204
    resp = await client.get(
        f"/api/v1/queues/{q['id']}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 404


# ── Pause / Resume ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_pause_and_resume_queue(client):
    token, pid = await _register(client, "q7@example.com", "Q Org 7")
    q = await _create_queue(client, token, pid)
    headers = {"Authorization": f"Bearer {token}"}

    # Pause
    resp = await client.post(f"/api/v1/queues/{q['id']}/pause", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["is_paused"] is True

    # Verify persisted
    resp = await client.get(f"/api/v1/queues/{q['id']}", headers=headers)
    assert resp.json()["data"]["is_paused"] is True

    # Resume
    resp = await client.post(f"/api/v1/queues/{q['id']}/resume", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["is_paused"] is False


# ── Validation ────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_invalid_concurrency_rejected(client):
    token, pid = await _register(client, "q8@example.com", "Q Org 8")
    resp = await client.post(
        f"/api/v1/projects/{pid}/queues",
        json={"name": "bad", "concurrency_limit": 0},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_invalid_priority_rejected(client):
    token, pid = await _register(client, "q9@example.com", "Q Org 9")
    resp = await client.post(
        f"/api/v1/projects/{pid}/queues",
        json={"name": "bad", "priority": 15},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_invalid_retry_policy_rejected(client):
    token, pid = await _register(client, "q10@example.com", "Q Org 10")
    resp = await client.post(
        f"/api/v1/projects/{pid}/queues",
        json={"name": "bad", "retry_policy": {"strategy": "exponential", "max_attempts": 0, "base_delay_s": 5, "max_delay_s": 3600}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422


# ── Isolation ─────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_queue_isolation_across_orgs(client):
    token_a, pid_a = await _register(client, "qa@example.com", "Org QA")
    token_b, _ = await _register(client, "qb@example.com", "Org QB")

    q = await _create_queue(client, token_a, pid_a)

    # Org B cannot access org A's queue
    resp = await client.get(
        f"/api/v1/queues/{q['id']}",
        headers={"Authorization": f"Bearer {token_b}"},
    )
    assert resp.status_code == 404
