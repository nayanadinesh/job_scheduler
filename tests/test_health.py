import pytest


@pytest.mark.asyncio
async def test_liveness(client):
    resp = await client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_readiness(client):
    resp = await client.get("/readyz")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["database"] == "reachable"


@pytest.mark.asyncio
async def test_unknown_route_returns_404(client):
    resp = await client.get("/nonexistent")
    assert resp.status_code == 404
