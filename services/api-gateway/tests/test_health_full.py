"""Tests for /health/full deep dependency checks (G28)."""
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


class TestHealthFull:
    @pytest.mark.asyncio
    async def test_health_full_returns_200(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health/full")
            assert resp.status_code == 200
            data = resp.json()
            assert "status" in data
            assert "checks" in data
            assert data["service"] == "api-gateway"

    @pytest.mark.asyncio
    async def test_health_full_has_all_checks(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health/full")
            data = resp.json()
            checks = data["checks"]
            assert "postgres" in checks
            assert "redis" in checks
            assert "nats" in checks
            assert "ai_engine" in checks

    @pytest.mark.asyncio
    async def test_health_basic_still_works(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health")
            assert resp.status_code == 200
            assert resp.json()["status"] == "healthy"
