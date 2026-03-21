"""Tenant context middleware - extracts tenant from JWT and sets context"""
from typing import Optional
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from contextvars import ContextVar

tenant_ctx: ContextVar[Optional[str]] = ContextVar("tenant_id", default=None)

PUBLIC_PATHS = {"/health", "/api/docs", "/api/redoc", "/api/v1/openapi.json", "/api/v1/auth/login"}


class TenantMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path in PUBLIC_PATHS or request.url.path.startswith("/api/v1/auth"):
            return await call_next(request)

        tid = request.state.__dict__.get("tenant_id")
        if tid:
            tenant_ctx.set(tid)
        return await call_next(request)


def get_current_tenant() -> Optional[str]:
    return tenant_ctx.get()
