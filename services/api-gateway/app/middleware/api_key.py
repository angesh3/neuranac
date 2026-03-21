"""API Key authentication middleware for service accounts and integrations.

Supports two modes:
  1. Header-based: X-API-Key header
  2. Bearer prefix: Authorization: ApiKey <key>

API keys are stored hashed in the database (api_keys table) and cached in
Redis for performance.  Each key is scoped to a tenant and carries a set of
permissions identical to RBAC roles.
"""

import hashlib
import time
from typing import Optional

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.database.redis import get_redis, safe_redis_op

logger = structlog.get_logger()

# Paths that never require API key auth (handled by JWT middleware)
BYPASS_PREFIXES = ("/health", "/ready", "/metrics", "/api/docs", "/api/openapi.json")

API_KEY_CACHE_TTL = 300  # 5 minutes


def hash_api_key(raw_key: str) -> str:
    """SHA-256 hash of an API key for storage and lookup."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Authenticate requests using API keys as an alternative to JWT.

    If an API key is present, it takes precedence.  If no API key header is
    found the request passes through so the JWT middleware can handle it.
    """

    async def dispatch(self, request: Request, call_next):
        # Skip paths that don't need auth
        if any(request.url.path.startswith(p) for p in BYPASS_PREFIXES):
            return await call_next(request)

        api_key = self._extract_key(request)
        if api_key is None:
            # No API key — fall through to JWT auth
            return await call_next(request)

        # Validate key
        key_info = await self._validate_key(api_key)
        if key_info is None:
            return JSONResponse(
                {"detail": "Invalid or expired API key"},
                status_code=401,
            )

        # Attach identity to request state so downstream code can use it
        request.state.user_id = key_info.get("service_account_id", "api-key-user")
        request.state.tenant_id = key_info.get("tenant_id")
        request.state.role = key_info.get("role", "api-client")
        request.state.permissions = key_info.get("permissions", [])
        request.state.auth_method = "api_key"

        return await call_next(request)

    @staticmethod
    def _extract_key(request: Request) -> Optional[str]:
        # X-API-Key header
        key = request.headers.get("X-API-Key")
        if key:
            return key

        # Authorization: ApiKey <key>
        auth = request.headers.get("Authorization", "")
        if auth.lower().startswith("apikey "):
            return auth[7:].strip()

        return None

    @staticmethod
    async def _validate_key(raw_key: str) -> Optional[dict]:
        key_hash = hash_api_key(raw_key)

        # Check Redis cache first
        redis = get_redis()
        if redis:
            cached = await safe_redis_op(redis.get(f"api_key:{key_hash}"))
            if cached == "invalid":
                return None
            if cached:
                import json
                return json.loads(cached)

        # DB lookup
        try:
            from app.database.session import async_session_factory
            if async_session_factory is None:
                return None

            from sqlalchemy import text
            async with async_session_factory() as session:
                result = await session.execute(
                    text(
                        "SELECT id, tenant_id, name, permissions, role, expires_at, is_active "
                        "FROM api_keys WHERE key_hash = :kh"
                    ),
                    {"kh": key_hash},
                )
                row = result.fetchone()
                if row is None:
                    # Cache negative result
                    if redis:
                        await safe_redis_op(
                            redis.set(f"api_key:{key_hash}", "invalid", ex=60)
                        )
                    return None

                if not row.is_active:
                    return None

                # Check expiry
                if row.expires_at and row.expires_at.timestamp() < time.time():
                    return None

                info = {
                    "service_account_id": str(row.id),
                    "tenant_id": str(row.tenant_id),
                    "name": row.name,
                    "permissions": row.permissions or [],
                    "role": row.role or "api-client",
                }

                # Cache positive result
                if redis:
                    import json
                    await safe_redis_op(
                        redis.set(
                            f"api_key:{key_hash}",
                            json.dumps(info),
                            ex=API_KEY_CACHE_TTL,
                        )
                    )

                return info
        except Exception as exc:
            logger.warning("API key validation error", error=str(exc))
            return None
