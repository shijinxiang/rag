"""Authentication API and JWT behavior tests."""
import pytest


@pytest.mark.asyncio
async def test_register_login_and_me(async_client, test_engine):
    from app.api.v1.auth import get_current_user
    from app.main import app
    app.dependency_overrides.pop(get_current_user, None)
    response = await async_client.post(
        "/api/v1/auth/register",
        json={"username": "alice", "email": "alice@example.com", "password": "secret-pass-123", "department": "hr"},
    )
    assert response.status_code == 201
    tokens = response.json()
    assert tokens["access_token"]
    assert tokens["refresh_token"]
    assert tokens["user"]["role"] == "employee"
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.user import User

    async with AsyncSession(test_engine) as independent_session:
        assert await independent_session.scalar(select(User.id).where(User.username == "alice")) is not None

    me = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {tokens['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["username"] == "alice"

    login = await async_client.post(
        "/api/v1/auth/login",
        json={"username": "alice", "password": "secret-pass-123"},
    )
    assert login.status_code == 200


@pytest.mark.asyncio
async def test_auth_rejects_bad_credentials_and_missing_token(async_client):
    from app.api.v1.auth import get_current_user
    from app.main import app
    app.dependency_overrides.pop(get_current_user, None)
    response = await async_client.post(
        "/api/v1/auth/register",
        json={"username": "bob", "email": "bob@example.com", "password": "secret-pass-123"},
    )
    assert response.status_code == 201

    bad_login = await async_client.post(
        "/api/v1/auth/login",
        json={"username": "bob", "password": "wrong-password"},
    )
    assert bad_login.status_code == 401
    assert (await async_client.get("/api/v1/auth/me")).status_code == 401


@pytest.mark.asyncio
async def test_refresh_token(async_client):
    register = await async_client.post(
        "/api/v1/auth/register",
        json={"username": "carol", "email": "carol@example.com", "password": "secret-pass-123"},
    )
    refreshed = await async_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": register.json()["refresh_token"]},
    )
    assert refreshed.status_code == 200
    assert refreshed.json()["access_token"]


@pytest.mark.asyncio
async def test_documents_and_queries_require_authentication(async_client):
    from app.api.v1.auth import get_current_user
    from app.main import app

    app.dependency_overrides.pop(get_current_user, None)
    assert (await async_client.get("/api/v1/documents")).status_code == 401
    assert (await async_client.post("/api/v1/queries", json={"question": "test"})).status_code == 401
