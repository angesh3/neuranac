"""Tests for API Key, Rate Limit, and Input Validation middleware (G8-G10)."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from starlette.testclient import TestClient
from fastapi import FastAPI, Request
from starlette.responses import JSONResponse

# --- Validation helpers (pure functions, no middleware wiring needed) ---

from app.middleware.validation import (
    _is_malicious,
    sanitize_string,
    validate_mac_address,
    validate_ip_address,
    validate_subnet,
)
from app.middleware.api_key import hash_api_key, BYPASS_PREFIXES, APIKeyMiddleware
from app.middleware.rate_limit import _get_endpoint_prefix, _get_rate_limit, DEFAULT_RATE


# ========== G10: Input Validation Tests ==========

class TestIsMalicious:
    def test_empty_string(self):
        assert _is_malicious("") is False

    def test_short_string(self):
        assert _is_malicious("ab") is False

    def test_normal_string(self):
        assert _is_malicious("hello world") is False

    def test_sql_union_select(self):
        assert _is_malicious("UNION SELECT * FROM users") is True

    def test_sql_drop_table(self):
        assert _is_malicious("-- DROP TABLE users") is True

    def test_sql_or_injection(self):
        assert _is_malicious("' OR '1'='1") is True

    def test_xss_script_tag(self):
        assert _is_malicious("<script>alert(1)</script>") is True

    def test_xss_javascript_uri(self):
        assert _is_malicious("javascript: alert(1)") is True

    def test_xss_event_handler(self):
        assert _is_malicious('onerror=alert(1)') is True

    def test_xss_iframe(self):
        assert _is_malicious("<iframe src='evil.com'>") is True

    def test_safe_json(self):
        assert _is_malicious('{"username": "alice", "role": "admin"}') is False

    def test_safe_sql_keywords_in_values(self):
        # "select" alone without FROM should not trigger
        assert _is_malicious("please select an option") is False


class TestSanitizeString:
    def test_empty(self):
        assert sanitize_string("") == ""

    def test_none(self):
        assert sanitize_string(None) is None

    def test_removes_angle_brackets(self):
        assert "<" not in sanitize_string("<script>alert(1)</script>")

    def test_truncates(self):
        long = "a" * 2000
        assert len(sanitize_string(long, max_length=100)) == 100

    def test_strips_whitespace(self):
        assert sanitize_string("  hello  ") == "hello"


class TestValidateMAC:
    def test_colon_format(self):
        assert validate_mac_address("AA:BB:CC:DD:EE:FF") is True

    def test_dash_format(self):
        assert validate_mac_address("AA-BB-CC-DD-EE-FF") is True

    def test_dot_format(self):
        assert validate_mac_address("AABB.CCDD.EEFF") is True

    def test_plain_format(self):
        assert validate_mac_address("AABBCCDDEEFF") is True

    def test_lowercase(self):
        assert validate_mac_address("aa:bb:cc:dd:ee:ff") is True

    def test_invalid_short(self):
        assert validate_mac_address("AA:BB:CC") is False

    def test_invalid_chars(self):
        assert validate_mac_address("GG:HH:II:JJ:KK:LL") is False

    def test_empty(self):
        assert validate_mac_address("") is False


class TestValidateIP:
    def test_ipv4(self):
        assert validate_ip_address("192.168.1.1") is True

    def test_ipv6(self):
        assert validate_ip_address("::1") is True

    def test_invalid(self):
        assert validate_ip_address("not-an-ip") is False

    def test_empty(self):
        assert validate_ip_address("") is False


class TestValidateSubnet:
    def test_cidr_v4(self):
        assert validate_subnet("10.0.0.0/8") is True

    def test_cidr_v6(self):
        assert validate_subnet("fe80::/10") is True

    def test_invalid(self):
        assert validate_subnet("not-a-subnet") is False


# ========== G8: API Key Middleware Tests ==========

class TestHashAPIKey:
    def test_deterministic(self):
        assert hash_api_key("my-key") == hash_api_key("my-key")

    def test_different_keys(self):
        assert hash_api_key("key1") != hash_api_key("key2")

    def test_returns_hex(self):
        h = hash_api_key("test")
        assert len(h) == 64  # SHA-256 hex digest


class TestAPIKeyExtraction:
    def test_extract_from_x_api_key_header(self):
        request = MagicMock()
        request.headers = {"X-API-Key": "test-key-123"}
        assert APIKeyMiddleware._extract_key(request) == "test-key-123"

    def test_extract_from_authorization_header(self):
        request = MagicMock()
        headers = MagicMock()
        headers.get = MagicMock(side_effect=lambda k, d="": {"Authorization": "ApiKey secret-key-456"}.get(k, d))
        request.headers = headers
        assert APIKeyMiddleware._extract_key(request) == "secret-key-456"

    def test_no_key_present(self):
        request = MagicMock()
        headers = MagicMock()
        headers.get = MagicMock(return_value="")
        request.headers = headers
        assert APIKeyMiddleware._extract_key(request) is None

    def test_bypass_paths(self):
        for path in BYPASS_PREFIXES:
            assert path.startswith("/")


# ========== G9: Rate Limit Tests ==========

class TestGetEndpointPrefix:
    def test_three_segments(self):
        assert _get_endpoint_prefix("/api/v1/auth/login") == "/api/v1/auth"

    def test_exact_three(self):
        assert _get_endpoint_prefix("/api/v1/policies") == "/api/v1/policies"

    def test_short_path(self):
        assert _get_endpoint_prefix("/health") == "/health"

    def test_deep_path(self):
        assert _get_endpoint_prefix("/api/v1/sessions/abc/details") == "/api/v1/sessions"


class TestGetRateLimit:
    def test_auth_limit(self):
        assert _get_rate_limit("/api/v1/auth") == 30

    def test_ai_limit(self):
        assert _get_rate_limit("/api/v1/ai") == 200

    def test_diagnostics_limit(self):
        assert _get_rate_limit("/api/v1/diagnostics") == 60

    def test_default_limit(self):
        assert _get_rate_limit("/api/v1/policies") == DEFAULT_RATE

    def test_unknown_path(self):
        assert _get_rate_limit("/something/else") == DEFAULT_RATE


# ========== Integration-style middleware tests using FastAPI TestClient ==========

def _make_app_with_validation():
    """Create a minimal FastAPI app with only validation middleware."""
    from app.middleware.validation import InputValidationMiddleware

    app = FastAPI()
    app.add_middleware(InputValidationMiddleware)

    @app.get("/test")
    async def test_endpoint():
        return {"status": "ok"}

    @app.post("/test")
    async def test_post(request: Request):
        return {"status": "ok"}

    return app


class TestValidationMiddlewareIntegration:
    def setup_method(self):
        self.app = _make_app_with_validation()
        self.client = TestClient(self.app)

    def test_clean_request_passes(self):
        resp = self.client.get("/test")
        assert resp.status_code == 200

    def test_sql_injection_in_query_blocked(self):
        resp = self.client.get("/test?q=UNION SELECT * FROM users")
        assert resp.status_code == 400
        assert "malicious" in resp.json()["error"].lower()

    def test_xss_in_query_blocked(self):
        resp = self.client.get("/test?q=<script>alert(1)</script>")
        assert resp.status_code == 400

    def test_oversized_content_length_blocked(self):
        resp = self.client.post(
            "/test",
            headers={"content-length": str(20 * 1024 * 1024), "content-type": "application/json"},
            content=b"{}",
        )
        assert resp.status_code == 413

    def test_normal_post_passes(self):
        resp = self.client.post(
            "/test",
            headers={"content-type": "application/json"},
            content=b'{"name": "test"}',
        )
        assert resp.status_code == 200
