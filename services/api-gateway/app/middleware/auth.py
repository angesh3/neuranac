"""JWT Authentication middleware"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
import structlog

from app.config import get_settings

logger = structlog.get_logger()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

import os
INTERNAL_SERVICE_KEY = os.getenv("INTERNAL_SERVICE_KEY", "neuranac_internal_dev_key_change_in_production")

PUBLIC_PATHS = {
    "/health", "/ready", "/metrics",
    "/api/v1/health", "/api/v1/ready", "/api/v1/health/full",
    "/api/docs", "/api/redoc", "/api/v1/openapi.json",
    "/api/v1/auth/login", "/api/v1/auth/refresh",
    "/api/v1/setup/status",
}

PUBLIC_PREFIXES = (
    "/api/v1/guest/portal",
    "/api/v1/setup/",
    "/api/v1/connectors/activate",
    "/api/v1/connectors/register",
)


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        method = request.method

        # Allow CORS preflight
        if method == "OPTIONS":
            return await call_next(request)

        # Allow public paths
        if path in PUBLIC_PATHS:
            return await call_next(request)
        for prefix in PUBLIC_PREFIXES:
            if path.startswith(prefix):
                return await call_next(request)

        # Allow internal service-to-service calls (AI Engine, etc.)
        internal_key = request.headers.get("X-Internal-Service-Key", "")
        if internal_key and internal_key == INTERNAL_SERVICE_KEY:
            request.state.user_id = "system:ai-engine"
            request.state.tenant_id = None
            request.state.roles = ["admin"]
            request.state.permissions = ["admin:super"]
            return await call_next(request)

        # Non-API paths (frontend static, etc.) pass through
        if not path.startswith("/api/"):
            return await call_next(request)

        # Extract token from header or cookie
        token = request.headers.get("Authorization", "").replace("Bearer ", "")
        if not token:
            token = request.cookies.get("access_token", "")

        if not token:
            return JSONResponse(
                status_code=401,
                content={"error": "Authentication required", "status_code": 401},
            )

        try:
            payload = decode_token(token)
            request.state.user_id = payload.get("sub")
            request.state.tenant_id = payload.get("tenant_id")
            request.state.roles = payload.get("roles", [])
            request.state.permissions = payload.get("permissions", [])
        except HTTPException:
            return JSONResponse(
                status_code=401,
                content={"error": "Invalid or expired token", "status_code": 401},
            )

        # Check if user's tokens have been revoked (blocklist)
        user_id = request.state.user_id
        if user_id:
            try:
                from app.database.redis import get_redis
                rdb = get_redis()
                if rdb and await rdb.exists(f"user_blocked:{user_id}"):
                    return JSONResponse(
                        status_code=401,
                        content={"error": "Token revoked", "status_code": 401},
                    )
            except Exception:
                pass  # Redis unavailable — degrade gracefully

        return await call_next(request)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    settings = get_settings()
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.jwt_access_token_expire_minutes))
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.jwt_signing_key, algorithm=settings.jwt_algorithm)


def create_refresh_token(data: dict, family_id: Optional[str] = None) -> str:
    settings = get_settings()
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(days=settings.jwt_refresh_token_expire_days)
    jti = str(uuid.uuid4())
    if not family_id:
        family_id = str(uuid.uuid4())
    to_encode.update({"exp": expire, "type": "refresh", "jti": jti, "family": family_id})
    return jwt.encode(to_encode, settings.jwt_signing_key, algorithm=settings.jwt_algorithm)


async def store_refresh_token(jti: str, family_id: str, user_id: str, ttl_days: int = 7):
    """Store refresh token JTI in Redis for rotation tracking."""
    from app.database.redis import get_redis
    rdb = get_redis()
    if not rdb:
        return
    ttl = ttl_days * 86400
    await rdb.setex(f"rt:{jti}", ttl, f"{family_id}:{user_id}")
    await rdb.sadd(f"rt_family:{family_id}", jti)
    await rdb.expire(f"rt_family:{family_id}", ttl)
    # Maintain user→families index for revoke_user_tokens()
    await rdb.sadd(f"user_rt_families:{user_id}", family_id)
    await rdb.expire(f"user_rt_families:{user_id}", ttl)


async def validate_and_rotate_refresh(token: str) -> dict:
    """Validate refresh token, revoke old, detect reuse. Returns token data."""
    from app.database.redis import get_redis
    payload = decode_token(token)
    if payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    jti = payload.get("jti")
    family_id = payload.get("family")
    user_id = payload.get("sub", "")

    rdb = get_redis()
    if rdb and jti and family_id:
        # Check if this JTI is still valid
        stored = await rdb.get(f"rt:{jti}")
        if stored is None:
            # Token was already used or revoked — possible token theft
            # Revoke entire family
            await revoke_token_family(family_id)
            logger.warning("Refresh token reuse detected", family=family_id, user=user_id)
            raise HTTPException(status_code=401, detail="Refresh token reuse detected, family revoked")
        # Invalidate this specific token (rotation)
        await rdb.delete(f"rt:{jti}")

    return payload


async def revoke_token_family(family_id: str):
    """Revoke all refresh tokens in a family (used on reuse detection or logout)."""
    from app.database.redis import get_redis
    rdb = get_redis()
    if not rdb:
        return
    members = await rdb.smembers(f"rt_family:{family_id}")
    if members:
        pipe = rdb.pipeline()
        for jti in members:
            pipe.delete(f"rt:{jti}")
        pipe.delete(f"rt_family:{family_id}")
        await pipe.execute()


async def revoke_user_tokens(user_id: str):
    """Revoke all refresh tokens for a user (password change, account disable, etc).

    Uses a per-user family index (``user_rt_families:<user_id>``) so we can
    enumerate every token family that belongs to this user and revoke them all.
    Also adds the user to a short-lived blocklist so outstanding access tokens
    are rejected until they naturally expire.
    """
    from app.database.redis import get_redis
    rdb = get_redis()
    if not rdb:
        logger.warning("Redis unavailable — cannot revoke tokens", user_id=user_id)
        return

    # 1. Revoke every refresh-token family belonging to this user
    family_ids = await rdb.smembers(f"user_rt_families:{user_id}")
    if family_ids:
        pipe = rdb.pipeline()
        for fid in family_ids:
            fid_str = fid if isinstance(fid, str) else fid.decode()
            # Delete every JTI in the family
            jtis = await rdb.smembers(f"rt_family:{fid_str}")
            for jti in jtis:
                jti_str = jti if isinstance(jti, str) else jti.decode()
                pipe.delete(f"rt:{jti_str}")
            pipe.delete(f"rt_family:{fid_str}")
        pipe.delete(f"user_rt_families:{user_id}")
        await pipe.execute()

    # 2. Blocklist the user's access tokens for the remaining access-token TTL
    settings = get_settings()
    ttl = settings.jwt_access_token_expire_minutes * 60
    await rdb.setex(f"user_blocked:{user_id}", ttl, "1")

    logger.info("User tokens revoked", user_id=user_id,
                families_revoked=len(family_ids) if family_ids else 0)


def decode_token(token: str) -> dict:
    settings = get_settings()
    try:
        payload = jwt.decode(token, settings.jwt_verify_key, algorithms=[settings.jwt_algorithm])
        return payload
    except JWTError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from e


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain[:72], hashed)


def hash_password(password: str) -> str:
    return pwd_context.hash(password[:72])


def require_permission(permission: str):
    """Dependency to check RBAC permission"""
    async def check(request: Request):
        permissions = getattr(request.state, "permissions", [])
        if permission not in permissions and "admin:super" not in permissions:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Missing permission: {permission}")
    return check


async def require_auth(request: Request):
    """Dependency that ensures the request has a valid authenticated user."""
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    return user_id
