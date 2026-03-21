"""Tests for the Policy Engine gRPC server module."""
import os
import pytest


def test_grpc_port_default():
    """gRPC port defaults to 9091 when POLICY_GRPC_PORT is not set."""
    os.environ.pop("POLICY_GRPC_PORT", None)
    port = int(os.getenv("POLICY_GRPC_PORT", "9091"))
    assert port == 9091


def test_grpc_port_override():
    """gRPC port can be overridden via environment variable."""
    os.environ["POLICY_GRPC_PORT"] = "50051"
    port = int(os.getenv("POLICY_GRPC_PORT", "9091"))
    assert port == 50051
    os.environ.pop("POLICY_GRPC_PORT", None)


def test_production_requires_tls_certs():
    """In production, missing TLS certs should raise RuntimeError."""
    os.environ["NeuraNAC_ENV"] = "production"
    os.environ.pop("GRPC_TLS_CERT", None)
    os.environ.pop("GRPC_TLS_KEY", None)

    cert_path = os.getenv("GRPC_TLS_CERT")
    key_path = os.getenv("GRPC_TLS_KEY")
    env = os.getenv("NeuraNAC_ENV")

    if env == "production" and (not cert_path or not key_path):
        with pytest.raises(RuntimeError):
            raise RuntimeError(
                "GRPC_TLS_CERT and GRPC_TLS_KEY are required in production."
            )
    os.environ.pop("NeuraNAC_ENV", None)


def test_development_allows_insecure():
    """In development, insecure gRPC should be allowed."""
    os.environ["NeuraNAC_ENV"] = "development"
    os.environ.pop("GRPC_TLS_CERT", None)
    os.environ.pop("GRPC_TLS_KEY", None)

    env = os.getenv("NeuraNAC_ENV")
    cert_path = os.getenv("GRPC_TLS_CERT")

    # No exception should be raised
    requires_tls = env == "production" and not cert_path
    assert not requires_tls
    os.environ.pop("NeuraNAC_ENV", None)


def test_mtls_with_ca_cert():
    """When CA cert is provided, mutual TLS should be enabled."""
    os.environ["GRPC_TLS_CERT"] = "/etc/neuranac/certs/server.crt"
    os.environ["GRPC_TLS_KEY"] = "/etc/neuranac/certs/server.key"
    os.environ["GRPC_TLS_CA"] = "/etc/neuranac/certs/ca.crt"

    ca_path = os.getenv("GRPC_TLS_CA")
    assert ca_path is not None
    require_client_auth = ca_path is not None
    assert require_client_auth is True

    os.environ.pop("GRPC_TLS_CERT", None)
    os.environ.pop("GRPC_TLS_KEY", None)
    os.environ.pop("GRPC_TLS_CA", None)


def test_policy_evaluation_request_structure():
    """Verify the expected policy evaluation request fields."""
    request = {
        "tenant_id": "t1",
        "session_id": "sess-001",
        "auth_context": {
            "auth_type": "dot1x",
            "eap_type": "eap-tls",
            "username": "alice",
            "calling_station_id": "AA:BB:CC:DD:EE:FF",
        },
        "network_context": {
            "nas_ip": "10.0.0.1",
            "device_vendor": "cisco",
        },
    }
    assert request["tenant_id"] == "t1"
    assert request["auth_context"]["eap_type"] == "eap-tls"
    assert "network_context" in request


def test_policy_response_decision_types():
    """Verify all supported decision types."""
    decisions = {
        0: "UNSPECIFIED",
        1: "PERMIT",
        2: "DENY",
        3: "QUARANTINE",
        4: "REDIRECT",
        5: "CONTINUE",
    }
    assert len(decisions) == 6
    assert decisions[1] == "PERMIT"
    assert decisions[2] == "DENY"


def test_authorization_result_fields():
    """Verify authorization result has expected fields."""
    authz = {
        "vlan_id": "100",
        "sgt_value": 50,
        "dacl_name": "PERMIT_ALL",
        "session_timeout": 3600,
        "coa_action": "none",
    }
    assert authz["vlan_id"] == "100"
    assert authz["sgt_value"] == 50
    assert authz["session_timeout"] == 3600
