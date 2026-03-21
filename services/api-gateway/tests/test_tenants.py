"""Tests for Tenant Management Router — CRUD, quotas, node allocation."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient


# ─── Mock DB helpers ─────────────────────────────────────────────────────────

def _mock_row(*values):
    """Create a mock row that supports index access."""
    row = MagicMock()
    row.__getitem__ = lambda self, i: values[i]
    row.__len__ = lambda self: len(values)
    return row


def _mock_result(rows=None, one=None):
    """Create a mock query result.

    Note: SQLAlchemy Result.fetchone()/fetchall() are synchronous,
    so this must be a MagicMock (not AsyncMock).
    """
    result = MagicMock()
    if one is not None:
        result.fetchone.return_value = one
    else:
        result.fetchone.return_value = rows[0] if rows else None
    result.fetchall.return_value = rows or []
    return result


# ─── Test Tenant Models ──────────────────────────────────────────────────────

def test_tenant_create_model():
    from app.routers.tenants import TenantCreate
    t = TenantCreate(name="Acme Corp", slug="acme-corp")
    assert t.name == "Acme Corp"
    assert t.slug == "acme-corp"
    assert t.isolation_mode == "row"
    assert t.tier == "standard"


def test_tenant_create_model_invalid_slug():
    from app.routers.tenants import TenantCreate
    with pytest.raises(Exception):
        TenantCreate(name="Bad", slug="BAD SLUG!")


def test_tenant_create_with_tier():
    from app.routers.tenants import TenantCreate
    t = TenantCreate(name="Enterprise", slug="enterprise-co", tier="enterprise",
                     isolation_mode="namespace")
    assert t.tier == "enterprise"
    assert t.isolation_mode == "namespace"


def test_quota_update_model():
    from app.routers.tenants import QuotaUpdate
    q = QuotaUpdate(max_nodes=50, tier="enterprise")
    assert q.max_nodes == 50
    assert q.tier == "enterprise"
    assert q.max_sites is None


def test_node_allocate_model():
    from app.routers.tenants import NodeAllocate
    n = NodeAllocate(node_id="node-uuid", tenant_id="tenant-uuid")
    assert n.node_id == "node-uuid"


# ─── Test Namespace Isolation ─────────────────────────────────────────────────

def test_tenant_namespace():
    from app.services.namespace_isolation import tenant_namespace
    assert tenant_namespace("acme-corp") == "neuranac-acme-corp"
    assert tenant_namespace("acme-corp", "bridge") == "neuranac-acme-corp-bridge"
    assert tenant_namespace("acme-corp", "data") == "neuranac-acme-corp-data"


def test_tenant_namespace_sanitization():
    from app.services.namespace_isolation import tenant_namespace
    assert tenant_namespace("UPPER_Case") == "neuranac-upper-case"
    assert tenant_namespace("special!@#chars") == "neuranac-special-chars"


def test_tenant_labels():
    from app.services.namespace_isolation import tenant_labels
    labels = tenant_labels("tid-123", "acme", "namespace")
    assert labels["neuranac.cisco.com/tenant-id"] == "tid-123"
    assert labels["neuranac.cisco.com/tenant-slug"] == "acme"
    assert labels["neuranac.cisco.com/isolation-mode"] == "namespace"
    assert labels["neuranac.cisco.com/managed-by"] == "neuranac-control-plane"


def test_tenant_network_policy():
    from app.services.namespace_isolation import tenant_network_policy
    policy = tenant_network_policy("tid-123", "acme")
    assert policy["kind"] == "NetworkPolicy"
    assert policy["metadata"]["namespace"] == "neuranac-acme"
    assert policy["spec"]["policyTypes"] == ["Ingress", "Egress"]


def test_tenant_resource_quota():
    from app.services.namespace_isolation import tenant_resource_quota
    quota = tenant_resource_quota("acme", "enterprise")
    assert quota["kind"] == "ResourceQuota"
    assert quota["spec"]["hard"]["requests.cpu"] == "32"
    assert quota["spec"]["hard"]["pods"] == "200"


def test_validate_namespace_ownership():
    from app.services.namespace_isolation import validate_namespace_ownership
    assert validate_namespace_ownership("neuranac-acme", "acme") is True
    assert validate_namespace_ownership("neuranac-acme-bridge", "acme") is True
    assert validate_namespace_ownership("neuranac-other", "acme") is False


# ─── Test Tenant Node Mapper ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_mapper_get_allocation_summary():
    from app.services.tenant_node_mapper import TenantNodeMapper
    db = AsyncMock()
    db.execute.return_value = _mock_result(one=_mock_row(20, 5, 1500, 45.2))

    mapper = TenantNodeMapper(db)
    summary = await mapper.get_allocation_summary("tenant-1")
    assert summary["max_nodes"] == 20
    assert summary["allocated"] == 5
    assert summary["remaining_quota"] == 15


@pytest.mark.asyncio
async def test_mapper_get_allocation_summary_no_quota():
    from app.services.tenant_node_mapper import TenantNodeMapper
    db = AsyncMock()
    db.execute.return_value = _mock_result(one=None)

    mapper = TenantNodeMapper(db)
    summary = await mapper.get_allocation_summary("no-tenant")
    assert summary["max_nodes"] == 0
    assert summary["allocated"] == 0


@pytest.mark.asyncio
async def test_mapper_find_available_nodes():
    from app.services.tenant_node_mapper import TenantNodeMapper
    db = AsyncMock()
    rows = [
        _mock_row("n1", "node-1", "s1", "worker", "pod-1", "ns-1", 20.0, 30.0, 5, "active"),
        _mock_row("n2", "node-2", "s1", "worker", "pod-2", "ns-1", 40.0, 50.0, 10, "active"),
    ]
    db.execute.return_value = _mock_result(rows=rows)

    mapper = TenantNodeMapper(db)
    nodes = await mapper.find_available_nodes()
    assert len(nodes) == 2
    assert nodes[0]["node_name"] == "node-1"


@pytest.mark.asyncio
async def test_mapper_auto_allocate_quota_exceeded():
    from app.services.tenant_node_mapper import TenantNodeMapper
    db = AsyncMock()
    # Return quota summary showing 0 remaining
    db.execute.return_value = _mock_result(one=_mock_row(5, 5, 100, 50.0))

    mapper = TenantNodeMapper(db)
    with pytest.raises(ValueError, match="quota remaining"):
        await mapper.auto_allocate("tenant-1", count=2)


# ─── Test Cert Issuer ─────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cert_issuer_issue_and_verify():
    from app.services.tenant_cert_issuer import TenantCertIssuer
    db = AsyncMock()
    db.execute.return_value = _mock_result(one=None)
    db.commit = AsyncMock()

    issuer = TenantCertIssuer(db)
    result = await issuer.issue_connector_cert(
        tenant_id="tid-111",
        connector_id="cid-222",
        connector_name="test-bridge",
    )
    assert "client_cert_pem" in result
    assert "client_key_pem" in result
    assert "ca_cert_pem" in result
    assert "fingerprint" in result
    assert result["client_cert_pem"].startswith("-----BEGIN CERTIFICATE-----")
    assert result["ca_cert_pem"].startswith("-----BEGIN CERTIFICATE-----")
    assert len(result["fingerprint"]) == 64  # SHA-256 hex


@pytest.mark.asyncio
async def test_cert_issuer_revoke():
    from app.services.tenant_cert_issuer import TenantCertIssuer
    db = AsyncMock()
    db.execute.return_value = _mock_result(rows=[_mock_row("trust-id")])
    db.commit = AsyncMock()

    issuer = TenantCertIssuer(db)
    result = await issuer.revoke_connector_cert("cid-222")
    assert result is True


@pytest.mark.asyncio
async def test_cert_issuer_verify_fingerprint_not_found():
    from app.services.tenant_cert_issuer import TenantCertIssuer
    db = AsyncMock()
    db.execute.return_value = _mock_result(one=None)

    issuer = TenantCertIssuer(db)
    result = await issuer.verify_fingerprint("nonexistent")
    assert result is None


# ─── Test Bridge Trust Middleware ─────────────────────────────────────────────

def test_bridge_trust_is_bridge_path():
    from app.middleware.bridge_trust import BridgeTrustMiddleware
    assert BridgeTrustMiddleware._is_bridge_path("/api/v1/connectors/register") is True
    assert BridgeTrustMiddleware._is_bridge_path("/api/v1/connectors/abc/heartbeat") is True
    assert BridgeTrustMiddleware._is_bridge_path("/api/v1/sites") is False
    assert BridgeTrustMiddleware._is_bridge_path("/health") is False
