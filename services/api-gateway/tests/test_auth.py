"""Tests for authentication endpoints"""
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.middleware.auth import create_access_token, create_refresh_token, hash_password, verify_password


@pytest.fixture
def test_token():
    return create_access_token({"sub": "test-user", "tenant_id": "test-tenant", "roles": ["admin"], "permissions": ["admin:super"]})


class TestPasswordHashing:
    def test_hash_and_verify(self):
        pwd = "testpassword123"
        hashed = hash_password(pwd)
        assert verify_password(pwd, hashed)
        assert not verify_password("wrongpassword", hashed)

    def test_different_hashes(self):
        pwd = "testpassword123"
        h1 = hash_password(pwd)
        h2 = hash_password(pwd)
        assert h1 != h2  # bcrypt uses random salt


class TestTokens:
    def test_create_access_token(self):
        token = create_access_token({"sub": "user1", "tenant_id": "t1"})
        assert isinstance(token, str)
        assert len(token) > 0

    def test_create_refresh_token(self):
        token = create_refresh_token({"sub": "user1", "tenant_id": "t1"})
        assert isinstance(token, str)
        assert len(token) > 0


class TestHealthEndpoint:
    @pytest.mark.asyncio
    async def test_health(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health")
            assert resp.status_code == 200
            data = resp.json()
            assert data["status"] == "healthy"
            assert data["service"] == "api-gateway"


class TestAuthEndpoints:
    @pytest.mark.asyncio
    async def test_login_missing_credentials(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/auth/login", json={})
            assert resp.status_code == 422

    @pytest.mark.asyncio
    async def test_logout(self, test_token):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {test_token}"})
            assert resp.status_code == 200
