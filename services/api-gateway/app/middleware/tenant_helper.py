"""Tenant helper — extracts tenant_id from request state for use in routers.

Usage in any router:
    from app.middleware.tenant_helper import get_tenant_id

    @router.post("/")
    async def create_thing(request: Request, db: AsyncSession = Depends(get_db)):
        tid = get_tenant_id(request)
        obj = MyModel(tenant_id=tid, ...)

This replaces all hardcoded '00000000-0000-0000-0000-000000000000' tenant_id values.
"""
from fastapi import Request

DEFAULT_TENANT_ID = "00000000-0000-0000-0000-000000000000"


def get_tenant_id(request: Request) -> str:
    """Extract tenant_id from the authenticated request state.

    The AuthMiddleware decodes the JWT and sets request.state.tenant_id.
    The TenantMiddleware then propagates it to the ContextVar.

    Falls back to the default tenant for:
      - Development environments without multi-tenant JWT setup
      - System-to-system calls (e.g., RADIUS → API Gateway) that don't carry tenant context
    """
    return getattr(request.state, "tenant_id", None) or DEFAULT_TENANT_ID
