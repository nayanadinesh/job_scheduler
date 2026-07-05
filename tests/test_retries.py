import pytest

from app.worker.backoff import compute_delay
from app.worker.pool import WorkerPool

# ── unit tests for backoff ────────────────────────────────────────────────────

def test_fixed_backoff():
    assert compute_delay("fixed", 10, 300, attempt=1) == 10
    assert compute_delay("fixed", 10, 300, attempt=5) == 10


def test_linear_backoff():
    assert compute_delay("linear", 5, 300, attempt=1) == 5
    assert compute_delay("linear", 5, 300, attempt=3) == 15


def test_exponential_backoff():
    assert compute_delay("exponential", 5, 300, attempt=1) == 5
    assert compute_delay("exponential", 5, 300, attempt=2) == 10
    assert compute_delay("exponential", 5, 300, attempt=3) == 20


def test_backoff_respects_max_delay():
    assert compute_delay("exponential", 5, 30, attempt=10) == 30


# ── helpers ───────────────────────────────────────────────────────────────────

async def _setup_with_retry_policy(client, email, org, max_attempts):
    reg = await client.post("/api/v1/auth/register", json={
        "email": email, "password": "securepass", "org_name": org,
    })
    token = reg.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    proj = await client.post("/api/v1/projects", json={"name": "RP"}, headers=headers)
    pid = proj.json()["data"]["id"]
    q = await client.post(
        f"/api/v1/projects/{pid}/queues",
        json={
            "name": "retry-q",
            "retry_policy": {
                "strategy": "exponential",
                "base_delay_s": 1,
                "max_attempts": max_attempts,
                "max_delay_s": 60,
            },
        },
        headers=headers,
    )
    return token, q.json()["data"]["id"]


async def _submit_failing(client, token, qid, duration_ms=5):
    resp = await client.post(
        f"/api/v1/queues/{qid}/jobs",
        json={"type": "fail-job", "payload": {"durationMs": duration_ms, "failRate": 1.0}},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 202
    return resp.json()["data"]


# ── integration: retry rescheduling ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_failed_job_is_rescheduled_when_attempts_remain(client, test_session_factory):
    token, qid = await _setup_with_retry_policy(client, "r1@example.com", "R Org 1", max_attempts=3)
    job = await _submit_failing(client, token, qid)

    pool = WorkerPool(queue_ids=[qid], session_factory=test_session_factory)
    await pool.process_batch(n=1)

    resp = await client.get(f"/api/v1/jobs/{job['id']}", headers={"Authorization": f"Bearer {token}"})
    data = resp.json()["data"]
    # One failure consumed → rescheduled for retry (attempts=1, back to queued)
    assert data["status"] == "queued"
    assert data["attempts"] == 1


@pytest.mark.asyncio
async def test_job_moves_to_dead_when_max_attempts_exhausted(client, test_session_factory):
    token, qid = await _setup_with_retry_policy(client, "r2@example.com", "R Org 2", max_attempts=1)
    job = await _submit_failing(client, token, qid)

    pool = WorkerPool(queue_ids=[qid], session_factory=test_session_factory)
    await pool.process_batch(n=1)

    resp = await client.get(f"/api/v1/jobs/{job['id']}", headers={"Authorization": f"Bearer {token}"})
    assert resp.json()["data"]["status"] == "dead"


@pytest.mark.asyncio
async def test_successful_job_completes_without_retry(client, test_session_factory):
    token, qid = await _setup_with_retry_policy(client, "r3@example.com", "R Org 3", max_attempts=3)
    resp = await client.post(
        f"/api/v1/queues/{qid}/jobs",
        json={"type": "good-job", "payload": {"durationMs": 5, "failRate": 0.0}},
        headers={"Authorization": f"Bearer {token}"},
    )
    job = resp.json()["data"]

    pool = WorkerPool(queue_ids=[qid], session_factory=test_session_factory)
    await pool.process_batch(n=1)

    resp2 = await client.get(f"/api/v1/jobs/{job['id']}", headers={"Authorization": f"Bearer {token}"})
    assert resp2.json()["data"]["status"] == "completed"


# ── DLQ re-queue ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_dead_job_can_be_manually_retried(client, test_session_factory):
    token, qid = await _setup_with_retry_policy(client, "r4@example.com", "R Org 4", max_attempts=1)
    job = await _submit_failing(client, token, qid)

    pool = WorkerPool(queue_ids=[qid], session_factory=test_session_factory)
    await pool.process_batch(n=1)  # → dead

    # Manual retry
    retry_resp = await client.post(
        f"/api/v1/jobs/{job['id']}/retry",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert retry_resp.status_code == 200
    assert retry_resp.json()["data"]["status"] == "queued"

    # Re-verify job state
    resp = await client.get(f"/api/v1/jobs/{job['id']}", headers={"Authorization": f"Bearer {token}"})
    data = resp.json()["data"]
    assert data["status"] == "queued"
    assert data["attempts"] == 0


@pytest.mark.asyncio
async def test_retry_non_dead_job_returns_409(client):
    # Re-use simple setup (no retry policy)
    reg = await client.post("/api/v1/auth/register", json={
        "email": "r5@example.com", "password": "securepass", "org_name": "R Org 5",
    })
    token = reg.json()["data"]["access_token"]
    proj = await client.post("/api/v1/projects", json={"name": "P"}, headers={"Authorization": f"Bearer {token}"})
    pid = proj.json()["data"]["id"]
    q = await client.post(f"/api/v1/projects/{pid}/queues", json={"name": "q"}, headers={"Authorization": f"Bearer {token}"})
    qid = q.json()["data"]["id"]

    job_resp = await client.post(
        f"/api/v1/queues/{qid}/jobs",
        json={"type": "job", "payload": {}},
        headers={"Authorization": f"Bearer {token}"},
    )
    job_id = job_resp.json()["data"]["id"]

    # Try to retry a queued (not dead) job
    resp = await client.post(
        f"/api/v1/jobs/{job_id}/retry",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409
