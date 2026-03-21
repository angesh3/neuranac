"""Integration tests for Federation Middleware — HMAC auth, circuit breaker, routing."""
import hashlib
import hmac
import time
import pytest
from unittest.mock import patch, AsyncMock, MagicMock

from starlette.testclient import TestClient
from fastapi import FastAPI
from starlette.responses import JSONResponse

from app.middleware.federation import (
    FederationMiddleware,
    _sign_request,
    _verify_signature,
    _PEER_FAILURE_THRESHOLD,
)


# ── HMAC signing tests ─────────────────────────────────────────────────────

def test_sign_request_deterministic():
    sig1 = _sign_request("secret", "GET", "/api/v1/nodes", "1234567890")
    sig2 = _sign_request("secret", "GET", "/api/v1/nodes", "1234567890")
    assert sig1 == sig2
    assert len(sig1) == 64  # SHA256 hex digest


def test_sign_request_different_secrets():
    sig1 = _sign_request("secret1", "GET", "/api/v1/nodes", "1234567890")
    sig2 = _sign_request("secret2", "GET", "/api/v1/nodes", "1234567890")
    assert sig1 != sig2


def test_verify_signature_valid():
    ts = str(time.time())
    sig = _sign_request("mysecret", "GET", "/api/v1/nodes", ts)
    assert _verify_signature("mysecret", "GET", "/api/v1/nodes", ts, sig) is True


def test_verify_signature_wrong_secret():
    ts = str(time.time())
    sig = _sign_request("mysecret", "GET", "/api/v1/nodes", ts)
    assert _verify_signature("wrong", "GET", "/api/v1/nodes", ts, sig) is False


def test_verify_signature_replay_protection():
    """Signatures older than 60s should be rejected."""
    ts = str(time.time() - 120)  # 2 minutes ago
    sig = _sign_request("mysecret", "GET", "/api/v1/nodes", ts)
    assert _verify_signature("mysecret", "GET", "/api/v1/nodes", ts, sig) is False


def test_verify_signature_invalid_timestamp():
    assert _verify_signature("s", "GET", "/", "not-a-number", "abc") is False
    assert _verify_signature("s", "GET", "/", "", "abc") is False


# ── Middleware routing tests ────────────────────────────────────────────────

def _make_test_app(deployment_mode="hybrid", peer_url="http://peer:8080", fed_secret="test_secret"):
    """Create a minimal FastAPI app with FederationMiddleware for testing."""
    app = FastAPI()

    mock_settings = MagicMock()
    mock_settings.deployment_mode = deployment_mode
    mock_settings.neuranac_peer_api_url = peer_url
    mock_settings.neuranac_site_id = "site-001"
    mock_settings.neuranac_site_type = "onprem"
    mock_settings.federation_shared_secret = fed_secret

    with patch("app.middleware.federation.get_settings", return_value=mock_settings):
        app.add_middleware(FederationMiddleware)

    @app.get("/api/v1/nodes")
    async def get_nodes():
        return {"items": [{"id": "local-1"}], "total": 1}

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    return app, mock_settings


def test_standalone_mode_skips_federation():
    """In standalone mode, X-NeuraNAC-Site header is ignored."""
    app, _ = _make_test_app(deployment_mode="standalone")
    client = TestClient(app)
    resp = client.get("/api/v1/nodes", headers={"X-NeuraNAC-Site": "peer"})
    assert resp.status_code == 200
    assert resp.json()["items"][0]["id"] == "local-1"


def test_local_site_header_handled_locally():
    """X-NeuraNAC-Site: local requests are handled locally."""
    app, _ = _make_test_app()
    client = TestClient(app)
    resp = client.get("/api/v1/nodes", headers={"X-NeuraNAC-Site": "local"})
    assert resp.status_code == 200
    assert resp.json()["items"][0]["id"] == "local-1"


def test_skip_paths_not_federated():
    """Health, auth, config paths are never federated."""
    app, _ = _make_test_app()
    client = TestClient(app)
    resp = client.get("/health", headers={"X-NeuraNAC-Site": "peer"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


def test_inbound_federated_request_requires_valid_sig():
    """Inbound federated requests with invalid signature are rejected."""
    app, settings = _make_test_app()
    with patch("app.middleware.federation.get_settings", return_value=settings):
        client = TestClient(app)
        resp = client.get(
            "/api/v1/nodes",
            headers={
                "x-neuranac-federated": "true",
                "x-neuranac-federation-sig": "invalid_sig",
                "x-neuranac-federation-ts": str(time.time()),
            },
        )
        assert resp.status_code == 403


def test_inbound_federated_request_valid_sig():
    """Inbound federated requests with valid signature pass through."""
    app, settings = _make_test_app()
    ts = str(time.time())
    sig = _sign_request("test_secret", "GET", "/api/v1/nodes", ts)
    with patch("app.middleware.federation.get_settings", return_value=settings):
        client = TestClient(app)
        resp = client.get(
            "/api/v1/nodes",
            headers={
                "x-neuranac-federated": "true",
                "x-neuranac-site": "local",
                "x-neuranac-federation-sig": sig,
                "x-neuranac-federation-ts": ts,
            },
        )
        assert resp.status_code == 200


# ── Per-scenario integration tests ────────────────────────────────────────

def test_scenario_s1_hybrid_legacy_nac_enabled():
    """S1: Hybrid + NeuraNAC — federation middleware active, local requests pass."""
    app, _ = _make_test_app(deployment_mode="hybrid", peer_url="http://peer:8080", fed_secret="s1secret")
    client = TestClient(app)
    resp = client.get("/api/v1/nodes", headers={"X-NeuraNAC-Site": "local"})
    assert resp.status_code == 200
    assert resp.json()["items"][0]["id"] == "local-1"


def test_scenario_s2_cloud_standalone():
    """S2: Cloud standalone — federation skipped, all requests local."""
    app, _ = _make_test_app(deployment_mode="standalone", peer_url="", fed_secret="")
    client = TestClient(app)
    resp = client.get("/api/v1/nodes", headers={"X-NeuraNAC-Site": "peer"})
    assert resp.status_code == 200
    assert resp.json()["items"][0]["id"] == "local-1"


def test_scenario_s3_onprem_standalone():
    """S3: On-prem standalone — federation skipped, peer header ignored."""
    app, _ = _make_test_app(deployment_mode="standalone", peer_url="", fed_secret="")
    client = TestClient(app)
    resp = client.get("/api/v1/nodes", headers={"X-NeuraNAC-Site": "all"})
    assert resp.status_code == 200


def test_scenario_s4_hybrid_no_ise():
    """S4: Hybrid no NeuraNAC — federation active, local requests work."""
    app, _ = _make_test_app(deployment_mode="hybrid", peer_url="http://peer:9080", fed_secret="s4secret")
    client = TestClient(app)
    resp = client.get("/api/v1/nodes", headers={"X-NeuraNAC-Site": "local"})
    assert resp.status_code == 200


def test_scenario_s4_no_peer_url_graceful():
    """S4: Hybrid with no peer URL configured — should not crash."""
    app, _ = _make_test_app(deployment_mode="hybrid", peer_url="", fed_secret="s4secret")
    client = TestClient(app)
    resp = client.get("/api/v1/nodes")
    assert resp.status_code == 200
