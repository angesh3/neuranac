"""Input validation middleware - sanitizes and validates incoming requests"""
import re
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

# Max request body size: 10MB
MAX_BODY_SIZE = 10 * 1024 * 1024

# Dangerous patterns for SQL injection and XSS
SQL_INJECTION_PATTERNS = [
    r"(\b(UNION|SELECT|INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|EXEC|EXECUTE)\b.*\b(FROM|INTO|TABLE|DATABASE|SET)\b)",
    r"(--|;)\s*(DROP|ALTER|DELETE|UPDATE|INSERT)",
    r"'\s*(OR|AND)\s*'?\d*'?\s*=\s*'?\d*",
    r"'\s*(OR|AND)\s+\d+\s*=\s*\d+",
]

XSS_PATTERNS = [
    r"<script[^>]*>",
    r"javascript\s*:",
    r"on(load|error|click|mouseover|focus|blur)\s*=",
    r"<iframe[^>]*>",
    r"<object[^>]*>",
    r"<embed[^>]*>",
]

# Compile patterns for performance
_sql_re = [re.compile(p, re.IGNORECASE) for p in SQL_INJECTION_PATTERNS]
_xss_re = [re.compile(p, re.IGNORECASE) for p in XSS_PATTERNS]


class InputValidationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Check Content-Length header
        content_length = request.headers.get("content-length")
        if content_length and int(content_length) > MAX_BODY_SIZE:
            return JSONResponse(
                status_code=413,
                content={"error": "Request body too large", "max_size_mb": MAX_BODY_SIZE // (1024 * 1024)},
            )

        # Validate query parameters
        for key, value in request.query_params.items():
            if _is_malicious(value):
                return JSONResponse(
                    status_code=400,
                    content={"error": "Potentially malicious input detected", "parameter": key},
                )

        # Validate path parameters
        path = request.url.path
        if _is_malicious(path):
            return JSONResponse(
                status_code=400,
                content={"error": "Potentially malicious path detected"},
            )

        # For JSON body requests, validate after reading
        if request.method in ("POST", "PUT", "PATCH"):
            content_type = request.headers.get("content-type", "")
            if "application/json" in content_type:
                try:
                    body = await request.body()
                    if len(body) > MAX_BODY_SIZE:
                        return JSONResponse(
                            status_code=413,
                            content={"error": "Request body too large"},
                        )
                    body_str = body.decode("utf-8", errors="replace")
                    if _is_malicious(body_str):
                        return JSONResponse(
                            status_code=400,
                            content={"error": "Potentially malicious content in request body"},
                        )
                except Exception:
                    pass

        return await call_next(request)


def _is_malicious(value: str) -> bool:
    """Check if a string contains SQL injection or XSS patterns."""
    if not value or len(value) < 3:
        return False
    for pattern in _sql_re:
        if pattern.search(value):
            return True
    for pattern in _xss_re:
        if pattern.search(value):
            return True
    return False


def sanitize_string(value: str, max_length: int = 1000) -> str:
    """Sanitize a string by removing dangerous characters and limiting length."""
    if not value:
        return value
    value = value[:max_length]
    value = re.sub(r'[<>"\']', '', value)
    return value.strip()


def validate_mac_address(mac: str) -> bool:
    """Validate MAC address format."""
    mac_patterns = [
        r'^([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}$',
        r'^([0-9A-Fa-f]{2}-){5}[0-9A-Fa-f]{2}$',
        r'^([0-9A-Fa-f]{4}\.){2}[0-9A-Fa-f]{4}$',
        r'^[0-9A-Fa-f]{12}$',
    ]
    return any(re.match(p, mac) for p in mac_patterns)


def validate_ip_address(ip: str) -> bool:
    """Validate IPv4 or IPv6 address."""
    import ipaddress
    try:
        ipaddress.ip_address(ip)
        return True
    except ValueError:
        return False


def validate_subnet(subnet: str) -> bool:
    """Validate CIDR subnet notation."""
    import ipaddress
    try:
        ipaddress.ip_network(subnet, strict=False)
        return True
    except ValueError:
        return False
