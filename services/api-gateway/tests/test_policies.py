"""Tests for policy endpoints"""
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.middleware.auth import create_access_token


@pytest.fixture
def auth_headers():
    token = create_access_token({"sub": "test", "tenant_id": "test", "roles": ["admin"], "permissions": ["admin:super"]})
    return {"Authorization": f"Bearer {token}"}


class TestPolicyEndpoints:
    @pytest.mark.asyncio
    async def test_list_policies(self, auth_headers):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/policies/", headers=auth_headers)
            assert resp.status_code == 200
            data = resp.json()
            assert "items" in data

    @pytest.mark.asyncio
    async def test_list_endpoints(self, auth_headers):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/endpoints/", headers=auth_headers)
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_list_network_devices(self, auth_headers):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/network-devices/", headers=auth_headers)
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_list_sessions(self, auth_headers):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/sessions/", headers=auth_headers)
            assert resp.status_code == 200
