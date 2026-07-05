import pytest


@pytest.mark.asyncio
async def test_register_creates_user_and_returns_token(client):
    resp = await client.post("/api/v1/auth/register", json={
        "email": "alice@example.com",
        "password": "securepass",
        "org_name": "Alice Corp",
    })
    assert resp.status_code == 201
    data = resp.json()["data"]
    assert data["user"]["email"] == "alice@example.com"
    assert "access_token" in data


@pytest.mark.asyncio
async def test_register_duplicate_email_returns_409(client):
    payload = {"email": "bob@example.com", "password": "securepass", "org_name": "Bob Corp"}
    await client.post("/api/v1/auth/register", json=payload)
    resp = await client.post("/api/v1/auth/register", json=payload)
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_register_short_password_rejected(client):
    resp = await client.post("/api/v1/auth/register", json={
        "email": "short@example.com",
        "password": "abc",
        "org_name": "X",
    })
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_login_returns_token(client):
    await client.post("/api/v1/auth/register", json={
        "email": "carol@example.com",
        "password": "securepass",
        "org_name": "Carol Corp",
    })
    resp = await client.post("/api/v1/auth/login", json={
        "email": "carol@example.com",
        "password": "securepass",
    })
    assert resp.status_code == 200
    assert "access_token" in resp.json()["data"]


@pytest.mark.asyncio
async def test_login_wrong_password_returns_401(client):
    await client.post("/api/v1/auth/register", json={
        "email": "dave@example.com",
        "password": "securepass",
        "org_name": "Dave Corp",
    })
    resp = await client.post("/api/v1/auth/login", json={
        "email": "dave@example.com",
        "password": "wrongpass",
    })
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_requires_auth(client):
    resp = await client.get("/api/v1/auth/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_returns_current_user(client):
    reg = await client.post("/api/v1/auth/register", json={
        "email": "eve@example.com",
        "password": "securepass",
        "org_name": "Eve Corp",
    })
    token = reg.json()["data"]["access_token"]
    resp = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["data"]["email"] == "eve@example.com"


@pytest.mark.asyncio
async def test_project_crud(client):
    reg = await client.post("/api/v1/auth/register", json={
        "email": "frank@example.com",
        "password": "securepass",
        "org_name": "Frank Corp",
    })
    token = reg.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Create
    resp = await client.post("/api/v1/projects", json={"name": "My Project"}, headers=headers)
    assert resp.status_code == 201
    project_id = resp.json()["data"]["id"]

    # List
    resp = await client.get("/api/v1/projects", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()["data"]) == 1

    # Get
    resp = await client.get(f"/api/v1/projects/{project_id}", headers=headers)
    assert resp.status_code == 200

    # Update
    resp = await client.patch(f"/api/v1/projects/{project_id}", json={"name": "Renamed"}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["data"]["name"] == "Renamed"

    # Delete
    resp = await client.delete(f"/api/v1/projects/{project_id}", headers=headers)
    assert resp.status_code == 204

    # Gone
    resp = await client.get(f"/api/v1/projects/{project_id}", headers=headers)
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_project_isolation_across_orgs(client):
    """User from org A cannot see org B's projects."""
    reg_a = await client.post("/api/v1/auth/register", json={
        "email": "orgA@example.com", "password": "securepass", "org_name": "Org A",
    })
    reg_b = await client.post("/api/v1/auth/register", json={
        "email": "orgB@example.com", "password": "securepass", "org_name": "Org B",
    })
    token_a = reg_a.json()["data"]["access_token"]
    token_b = reg_b.json()["data"]["access_token"]

    # Org A creates a project
    resp = await client.post("/api/v1/projects", json={"name": "A's Project"}, headers={"Authorization": f"Bearer {token_a}"})
    project_id = resp.json()["data"]["id"]

    # Org B cannot access it
    resp = await client.get(f"/api/v1/projects/{project_id}", headers={"Authorization": f"Bearer {token_b}"})
    assert resp.status_code == 404
