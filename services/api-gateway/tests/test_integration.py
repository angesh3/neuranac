"""Integration tests for NeuraNAC API Gateway.

These tests exercise full request/response cycles through the FastAPI app
using httpx AsyncClient with ASGITransport (no real DB or Redis needed
for route-level validation).
"""
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.middleware.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)


# ── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture
def admin_token():
    """JWT with admin:super permission."""
    return create_access_token({
        "sub": "test-admin",
        "tenant_id": "00000000-0000-0000-0000-000000000000",
        "roles": ["admin"],
        "permissions": ["admin:super"],
    })


@pytest.fixture
def readonly_token():
    """JWT with only read permissions."""
    return create_access_token({
        "sub": "test-reader",
        "tenant_id": "00000000-0000-0000-0000-000000000000",
        "roles": ["viewer"],
        "permissions": ["legacy_nac:read", "network:read"],
    })


@pytest.fixture
def refresh_tok():
    """A refresh token for rotation tests."""
    return create_refresh_token({
        "sub": "test-admin",
        "tenant_id": "00000000-0000-0000-0000-000000000000",
    })


def _headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ── Health & Public ──────────────────────────────────────────────────────────

class TestPublicEndpoints:
    @pytest.mark.asyncio
    async def test_health(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/health")
            assert r.status_code == 200
            assert r.json()["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_ready(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/ready")
            assert r.status_code in (200, 503)

    @pytest.mark.asyncio
    async def test_metrics(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/metrics")
            assert r.status_code == 200
            assert "text/plain" in r.headers.get("content-type", "")

    @pytest.mark.asyncio
    async def test_openapi_json(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/api/v1/openapi.json")
            assert r.status_code == 200
            data = r.json()
            assert "paths" in data
            assert "info" in data


# ── Auth ─────────────────────────────────────────────────────────────────────

class TestAuthFlow:
    @pytest.mark.asyncio
    async def test_login_invalid_body(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.post("/api/v1/auth/login", json={})
            assert r.status_code == 422

    @pytest.mark.asyncio
    async def test_protected_route_no_token(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/api/v1/admin/users")
            assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_protected_route_with_token(self, admin_token):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/api/v1/admin/users", headers=_headers(admin_token))
            # Should not be 401 — may be 200 or 500 depending on DB
            assert r.status_code != 401

    @pytest.mark.asyncio
    async def test_logout(self, admin_token):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.post("/api/v1/auth/logout", headers=_headers(admin_token))
            assert r.status_code == 200


# ── JWT RS256 ────────────────────────────────────────────────────────────────

class TestJWTRS256:
    def test_access_token_roundtrip(self):
        token = create_access_token({"sub": "u1", "tenant_id": "t1", "roles": [], "permissions": []})
        payload = decode_token(token)
        assert payload["sub"] == "u1"
        assert payload["type"] == "access"

    def test_refresh_token_roundtrip(self):
        token = create_refresh_token({"sub": "u2", "tenant_id": "t1"})
        payload = decode_token(token)
        assert payload["sub"] == "u2"
        assert payload["type"] == "refresh"
        assert "jti" in payload
        assert "family" in payload

    def test_password_hashing(self):
        hashed = hash_password("SecureP@ss1")
        assert verify_password("SecureP@ss1", hashed)
        assert not verify_password("wrong", hashed)


# ── RBAC / Permission ───────────────────────────────────────────────────────

class TestRBAC:
    @pytest.mark.asyncio
    async def test_admin_can_access_admin_routes(self, admin_token):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/api/v1/audit/logs", headers=_headers(admin_token))
            assert r.status_code != 403

    @pytest.mark.asyncio
    async def test_reader_cannot_write(self, readonly_token):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.post(
                "/api/v1/legacy-nac/connections",
                json={"name": "x", "hostname": "h", "port": 443, "username": "u", "password": "p"},
                headers=_headers(readonly_token),
            )
            assert r.status_code == 403


# ── Legacy Integration Routes ──────────────────────────────────────────────────

class TestNeuraNACRoutes:
    @pytest.mark.asyncio
    async def test_legacy_nac_summary(self, admin_token):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/api/v1/legacy-nac/summary", headers=_headers(admin_token))
            # May fail with DB error but should not be 401/403
            assert r.status_code != 401
            assert r.status_code != 403

    @pytest.mark.asyncio
    async def test_legacy_nac_connections_list(self, admin_token):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/api/v1/legacy-nac/connections", headers=_headers(admin_token))
            assert r.status_code != 401

    @pytest.mark.asyncio
    async def test_multi_legacy_nac_overview(self, admin_token):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/api/v1/legacy-nac/multi-legacy-nac/overview", headers=_headers(admin_token))
            assert r.status_code != 401


# ── Policy & Network Routes ─────────────────────────────────────────────────

class TestPolicyRoutes:
    @pytest.mark.asyncio
    async def test_policies_list(self, admin_token):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/api/v1/policies", headers=_headers(admin_token))
            assert r.status_code != 401

    @pytest.mark.asyncio
    async def test_network_devices_list(self, admin_token):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/api/v1/network-devices", headers=_headers(admin_token))
            assert r.status_code != 401

    @pytest.mark.asyncio
    async def test_sessions_list(self, admin_token):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/api/v1/sessions", headers=_headers(admin_token))
            assert r.status_code != 401

    @pytest.mark.asyncio
    async def test_endpoints_list(self, admin_token):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/api/v1/endpoints", headers=_headers(admin_token))
            assert r.status_code != 401


# ── Diagnostics ──────────────────────────────────────────────────────────────

class TestDiagnostics:
    @pytest.mark.asyncio
    async def test_diagnostics_routes_exist(self, admin_token):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/api/v1/diagnostics/db-schema-check", headers=_headers(admin_token))
            # Route must be registered (not 404) and pass auth (not 401)
            assert r.status_code != 401
            assert r.status_code != 404, f"db-schema-check route not found, got {r.status_code}"


# ── AI Chat Proxy ────────────────────────────────────────────────────────────

class TestAIChatProxy:
    @pytest.mark.asyncio
    async def test_ai_chat_proxy(self, admin_token):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.post(
                "/api/v1/ai/chat",
                json={"message": "show me all endpoints"},
                headers=_headers(admin_token),
            )
            # Proxy may fail if AI Engine is down, but should not be 401/403
            assert r.status_code != 401
            assert r.status_code != 403

    @pytest.mark.asyncio
    async def test_ai_suggestions(self, admin_token):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/api/v1/ai/suggestions", headers=_headers(admin_token))
            assert r.status_code != 401


# ── Setup Wizard (public) ───────────────────────────────────────────────────

class TestSetupWizard:
    @pytest.mark.asyncio
    async def test_setup_status_is_public(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.get("/api/v1/setup/status")
            assert r.status_code != 401


# ── CORS Headers ─────────────────────────────────────────────────────────────

class TestCORS:
    @pytest.mark.asyncio
    async def test_cors_preflight(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            r = await c.options(
                "/api/v1/policies",
                headers={
                    "Origin": "http://localhost:3001",
                    "Access-Control-Request-Method": "GET",
                },
            )
            assert r.status_code == 200
            assert "access-control-allow-origin" in r.headers
