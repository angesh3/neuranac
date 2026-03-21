"""Rate limiting middleware using Redis sliding window, keyed per-endpoint-prefix.

Supports per-tenant quota tiers loaded from request.state.tenant_quota_tier
(set by TenantMiddleware from neuranac_tenant_quotas).  Falls back to IP-based
limiting when no tenant context is available.
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
import time
import structlog

logger = structlog.get_logger()

EXEMPT_PATHS = {"/health", "/ready", "/metrics", "/api/docs", "/api/redoc"}

# Per-prefix rate limits (requests per minute) — used as base for IP-based limiting
ENDPOINT_LIMITS = {
    "/api/v1/auth":         30,   # auth: lower to prevent brute-force
    "/api/v1/ai":          200,   # AI: higher for chat
    "/api/v1/diagnostics":  60,
    "/api/v1/setup":        30,
}
DEFAULT_RATE = 100  # requests per minute for unlisted prefixes

# Per-tenant quota tiers — multiplier applied to endpoint limits
TENANT_TIER_MULTIPLIERS = {
    "free":       0.3,    # ~30 req/min on default endpoints
    "standard":   1.0,    # 100 req/min (baseline)
    "enterprise": 5.0,    # 500 req/min
    "unlimited":  100.0,  # 10000 req/min (effectively unlimited)
}


def _get_endpoint_prefix(path: str) -> str:
    """Extract the first 3 path segments as the rate-limit bucket key."""
    parts = path.strip("/").split("/")
    return "/" + "/".join(parts[:3]) if len(parts) >= 3 else path


def _get_rate_limit(prefix: str, tier: str = "") -> int:
    """Return the rate limit for a given endpoint prefix and tenant tier."""
    base = DEFAULT_RATE
    for pattern, limit in ENDPOINT_LIMITS.items():
        if prefix.startswith(pattern):
            base = limit
            break
    multiplier = TENANT_TIER_MULTIPLIERS.get(tier, 1.0)
    return max(1, int(base * multiplier))


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in EXEMPT_PATHS or request.method == "OPTIONS":
            return await call_next(request)

        from app.database.redis import get_redis
        rdb = get_redis()
        if not rdb:
            return await call_next(request)

        tenant_id = getattr(request.state, "tenant_id", None)
        tenant_tier = getattr(request.state, "tenant_quota_tier", "")
        client_ip = request.client.host if request.client else "unknown"
        identity = tenant_id or client_ip
        prefix = _get_endpoint_prefix(request.url.path)
        rate = _get_rate_limit(prefix, tenant_tier)

        try:
            pipe = rdb.pipeline()
            now = time.time()
            window_key = f"rl:{identity}:{prefix}:{int(now // 60)}"
            await pipe.incr(window_key)
            await pipe.expire(window_key, 120)
            results = await pipe.execute()
            count = results[0]
            remaining = max(0, rate - count)

            if count > rate:
                logger.warning("Rate limit exceeded",
                               identity=identity, tier=tenant_tier,
                               prefix=prefix, rate=rate, count=count)
                return JSONResponse(
                    status_code=429,
                    content={"error": "Rate limit exceeded", "retry_after": 60},
                    headers={
                        "Retry-After": "60",
                        "X-RateLimit-Limit": str(rate),
                        "X-RateLimit-Remaining": "0",
                    },
                )
        except Exception as e:
            logger.warning("Rate limit check failed", error=str(e))

        return await call_next(request)
