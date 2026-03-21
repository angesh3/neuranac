"""Web Application Firewall (WAF) middleware.

Provides defence-in-depth on top of the existing InputValidationMiddleware:
  - Path traversal detection
  - HTTP method enforcement
  - Header injection / CRLF detection
  - Request smuggling detection (conflicting Content-Length / Transfer-Encoding)
  - Known scanner / bot User-Agent blocking
  - Configurable block vs log-only mode via WAF_MODE env var (block | log)
"""
import os
import re
import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = structlog.get_logger()

WAF_MODE = os.getenv("WAF_MODE", "block")  # "block" or "log"

ALLOWED_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"}

# Path traversal patterns
_PATH_TRAVERSAL_RE = re.compile(
    r"(\.\./|\.\.\\|%2e%2e[/%5c]|%252e%252e|%c0%ae)", re.IGNORECASE
)

# CRLF injection in headers
_CRLF_RE = re.compile(r"[\r\n]|%0[da]|%0[DA]", re.IGNORECASE)

# Null byte injection
_NULL_BYTE_RE = re.compile(r"%00|\x00")

# Known malicious / scanner User-Agents (substrings, case-insensitive)
BAD_USER_AGENTS = [
    "sqlmap",
    "nikto",
    "nessus",
    "openvas",
    "masscan",
    "zgrab",
    "gobuster",
    "dirbuster",
    "wpscan",
    "acunetix",
    "netsparker",
    "burpsuite",
    "havij",
    "w3af",
]
_BAD_UA_RE = re.compile("|".join(BAD_USER_AGENTS), re.IGNORECASE)

EXEMPT_PATHS = {"/health", "/ready", "/metrics"}


class WAFMiddleware(BaseHTTPMiddleware):
    """Web Application Firewall — outermost middleware layer."""

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        method = request.method

        # Skip health endpoints
        if path in EXEMPT_PATHS:
            return await call_next(request)

        # 1. HTTP method enforcement
        if method not in ALLOWED_METHODS:
            return self._respond(request, "waf_method", f"Method {method} not allowed")

        # 2. Path traversal
        if _PATH_TRAVERSAL_RE.search(path):
            return self._respond(request, "waf_path_traversal", "Path traversal detected")

        # 3. Null byte in path or query
        full_url = str(request.url)
        if _NULL_BYTE_RE.search(full_url):
            return self._respond(request, "waf_null_byte", "Null byte injection detected")

        # 4. CRLF injection in headers
        for header_name, header_value in request.headers.items():
            if _CRLF_RE.search(header_value):
                return self._respond(
                    request, "waf_crlf",
                    f"CRLF injection detected in header {header_name}",
                )

        # 5. Request smuggling: conflicting Content-Length and Transfer-Encoding
        has_cl = "content-length" in request.headers
        has_te = "transfer-encoding" in request.headers
        if has_cl and has_te:
            return self._respond(
                request, "waf_smuggling",
                "Request smuggling: both Content-Length and Transfer-Encoding present",
            )

        # 6. Scanner / bot User-Agent
        ua = request.headers.get("user-agent", "")
        if ua and _BAD_UA_RE.search(ua):
            return self._respond(
                request, "waf_scanner",
                "Known scanner/bot User-Agent blocked",
            )

        return await call_next(request)

    def _respond(self, request: Request, rule: str, detail: str):
        client_ip = request.client.host if request.client else "unknown"
        logger.warning(
            "WAF violation",
            rule=rule,
            detail=detail,
            path=request.url.path,
            method=request.method,
            client_ip=client_ip,
            mode=WAF_MODE,
        )
        if WAF_MODE == "log":
            # Log-only mode: let the request through
            return None  # will fall through; caller must handle
        return JSONResponse(
            status_code=403,
            content={"error": "Forbidden", "rule": rule, "detail": detail},
        )

    async def dispatch(self, request: Request, call_next):  # noqa: F811
        path = request.url.path
        method = request.method

        if path in EXEMPT_PATHS:
            return await call_next(request)

        checks = [
            self._check_method(request, method),
            self._check_path_traversal(request, path),
            self._check_null_byte(request),
            self._check_crlf(request),
            self._check_smuggling(request),
            self._check_scanner(request),
        ]

        for result in checks:
            if result is not None:
                if WAF_MODE == "log":
                    break  # log-only — continue processing
                return result

        return await call_next(request)

    def _check_method(self, request, method):
        if method not in ALLOWED_METHODS:
            return self._respond(request, "waf_method", f"Method {method} not allowed")
        return None

    def _check_path_traversal(self, request, path):
        if _PATH_TRAVERSAL_RE.search(path):
            return self._respond(request, "waf_path_traversal", "Path traversal detected")
        return None

    def _check_null_byte(self, request):
        if _NULL_BYTE_RE.search(str(request.url)):
            return self._respond(request, "waf_null_byte", "Null byte injection detected")
        return None

    def _check_crlf(self, request):
        for name, value in request.headers.items():
            if _CRLF_RE.search(value):
                return self._respond(request, "waf_crlf", f"CRLF injection in header {name}")
        return None

    def _check_smuggling(self, request):
        has_cl = "content-length" in request.headers
        has_te = "transfer-encoding" in request.headers
        if has_cl and has_te:
            return self._respond(request, "waf_smuggling",
                                 "Both Content-Length and Transfer-Encoding present")
        return None

    def _check_scanner(self, request):
        ua = request.headers.get("user-agent", "")
        if ua and _BAD_UA_RE.search(ua):
            return self._respond(request, "waf_scanner", "Known scanner/bot blocked")
        return None
