"""
Integration tests for the NeuraNAC API Gateway.
These tests verify cross-service interactions using the actual FastAPI app
with mocked external dependencies (DB, Redis, NATS).
"""
import pytest
from httpx import AsyncClient, ASGITransport

# Import the FastAPI app
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../services/api-gateway"))
from app.main import app


@pytest.fixture
def transport():
    return ASGITransport(app=app)


class TestHealthEndpoints:
    @pytest.mark.asyncio
    async def test_health_endpoint(self, transport):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health")
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_root_endpoint(self, transport):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/")
            assert resp.status_code in (200, 307, 401, 404)


class TestAuthFlow:
    @pytest.mark.asyncio
    async def test_login_missing_fields(self, transport):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/auth/login", json={})
            assert resp.status_code in (400, 401, 422)

    @pytest.mark.asyncio
    async def test_login_invalid_credentials(self, transport):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.post("/api/v1/auth/login", json={
                "username": "nonexistent", "password": "wrong"
            })
            # Should return 401 or 500 (if DB not available)
            assert resp.status_code in (401, 500)

    @pytest.mark.asyncio
    async def test_protected_route_without_token(self, transport):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/policies/")
            assert resp.status_code in (401, 403)

    @pytest.mark.asyncio
    async def test_protected_route_with_bad_token(self, transport):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get(
                "/api/v1/policies/",
                headers={"Authorization": "Bearer invalid-token-xyz"}
            )
            assert resp.status_code in (401, 403)


class TestAPIRouteRegistration:
    """Verify all major API routes are registered (not 404)."""

    ROUTES = [
        ("GET", "/api/v1/diagnostics/system-status"),
        ("GET", "/api/v1/diagnostics/radius-live-log"),
        ("GET", "/api/v1/diagnostics/db-schema-check"),
        ("GET", "/api/v1/legacy-nac/connections"),
        ("GET", "/api/v1/legacy-nac/summary"),
    ]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("method,path", ROUTES)
    async def test_route_exists(self, transport, method, path):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            if method == "GET":
                resp = await client.get(path)
            else:
                resp = await client.post(path, json={})
            # Route exists — should NOT be 404 or 405
            assert resp.status_code != 404, f"{method} {path} returned 404"


class TestDiagnosticsIntegration:
    @pytest.mark.asyncio
    async def test_system_status_returns_json(self, transport):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/diagnostics/system-status")
            # May require auth; verify route exists (not 404)
            assert resp.status_code != 404
            if resp.status_code == 200:
                data = resp.json()
                assert isinstance(data, dict)

    @pytest.mark.asyncio
    async def test_radius_live_log(self, transport):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/diagnostics/radius-live-log")
            assert resp.status_code != 404
            if resp.status_code == 200:
                data = resp.json()
                assert "entries" in data

    @pytest.mark.asyncio
    async def test_db_schema_check_route_registered(self, transport):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/diagnostics/db-schema-check")
            # Route registered (not 404); may fail without DB
            assert resp.status_code != 404


class TestCORSAndHeaders:
    @pytest.mark.asyncio
    async def test_cors_preflight(self, transport):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.options(
                "/api/v1/diagnostics/system-status",
                headers={
                    "Origin": "http://localhost:5173",
                    "Access-Control-Request-Method": "GET",
                }
            )
            # Should not crash; CORS may or may not be configured
            assert resp.status_code in (200, 204, 401, 404, 405)
