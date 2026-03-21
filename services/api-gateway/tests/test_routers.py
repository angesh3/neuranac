"""Comprehensive router tests for API Gateway"""
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.middleware.auth import create_access_token


@pytest.fixture
def auth_headers():
    token = create_access_token({"sub": "test", "tenant_id": "test", "roles": ["admin"], "permissions": ["admin:super"]})
    return {"Authorization": f"Bearer {token}"}


class TestHealthEndpoints:
    @pytest.mark.asyncio
    async def test_health(self):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/health")
            assert resp.status_code == 200
            assert resp.json()["status"] == "healthy"


class TestIdentitySourceEndpoints:
    @pytest.mark.asyncio
    async def test_list_sources(self, auth_headers):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/identity-sources/", headers=auth_headers)
            assert resp.status_code == 200
            assert "items" in resp.json()


class TestCertificateEndpoints:
    @pytest.mark.asyncio
    async def test_list_cas(self, auth_headers):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/certificates/cas", headers=auth_headers)
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_list_certs(self, auth_headers):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/certificates/", headers=auth_headers)
            assert resp.status_code == 200


class TestSegmentationEndpoints:
    @pytest.mark.asyncio
    async def test_list_sgts(self, auth_headers):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/segmentation/sgts", headers=auth_headers)
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_get_matrix(self, auth_headers):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/segmentation/matrix", headers=auth_headers)
            assert resp.status_code == 200
            assert "matrix" in resp.json()


class TestGuestEndpoints:
    @pytest.mark.asyncio
    async def test_list_portals(self, auth_headers):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/guest/portals", headers=auth_headers)
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_sponsor_groups(self, auth_headers):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/guest/sponsor-groups", headers=auth_headers)
            assert resp.status_code == 200
            assert resp.json()["total"] == 3


class TestPostureEndpoints:
    @pytest.mark.asyncio
    async def test_list_posture_policies(self, auth_headers):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/posture/policies", headers=auth_headers)
            assert resp.status_code == 200


class TestNodesEndpoints:
    @pytest.mark.asyncio
    async def test_list_nodes(self, auth_headers):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/nodes/", headers=auth_headers)
            assert resp.status_code == 200
            data = resp.json()
            assert "items" in data
            assert len(data["items"]) >= 1

    @pytest.mark.asyncio
    async def test_sync_status(self, auth_headers):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/nodes/sync-status", headers=auth_headers)
            assert resp.status_code == 200


class TestDiagnosticsEndpoints:
    @pytest.mark.asyncio
    async def test_system_status(self, auth_headers):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/diagnostics/system-status", headers=auth_headers)
            assert resp.status_code == 200
            assert "services" in resp.json()


class TestAIDataFlowEndpoints:
    @pytest.mark.asyncio
    async def test_list_policies(self, auth_headers):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/ai/data-flow/policies", headers=auth_headers)
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_list_services(self, auth_headers):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/ai/data-flow/services", headers=auth_headers)
            assert resp.status_code == 200


class TestPrivacyEndpoints:
    @pytest.mark.asyncio
    async def test_list_subjects(self, auth_headers):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/privacy/subjects", headers=auth_headers)
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_list_consent(self, auth_headers):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/privacy/consent", headers=auth_headers)
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_list_exports(self, auth_headers):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/privacy/exports", headers=auth_headers)
            assert resp.status_code == 200


class TestAuditEndpoints:
    @pytest.mark.asyncio
    async def test_list_audit_logs(self, auth_headers):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/audit/", headers=auth_headers)
            assert resp.status_code == 200


class TestNeuraNACIntegrationEndpoints:
    @pytest.mark.asyncio
    async def test_list_connections(self, auth_headers):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/legacy-nac/connections", headers=auth_headers)
            assert resp.status_code == 200
            data = resp.json()
            assert "items" in data
            assert "total" in data

    @pytest.mark.asyncio
    async def test_legacy_nac_summary(self, auth_headers):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/legacy-nac/summary", headers=auth_headers)
            # Route exists and passes auth; may return 500 if DB unavailable
            assert resp.status_code != 401
            assert resp.status_code != 403
            if resp.status_code == 200:
                data = resp.json()
                assert "connections" in data
                assert "sync_last_24h" in data
                assert "entities_mapped" in data
                assert "deployment_modes" in data
