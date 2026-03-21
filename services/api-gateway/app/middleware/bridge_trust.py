"""Bridge Trust Verification Middleware — zero-trust mTLS validation for connectors.

Verifies that incoming requests from NeuraNAC Bridge instances carry valid client
certificates issued by the NeuraNAC internal CA. Extracts tenant_id from the
certificate's SPIFFE URI or fingerprint lookup.

Flow:
  1. Bridge presents client cert (via X-Client-Cert-Fingerprint header or TLS)
  2. Middleware looks up fingerprint in neuranac_connector_trust table
  3. If trusted + not expired: sets request.state.bridge_tenant_id, bridge_connector_id
  4. If untrusted/expired/missing: rejects with 403 (for bridge-only endpoints)

For non-bridge endpoints, this middleware is a no-op (passes through).
Bridge endpoints are identified by the /api/v1/connectors/ prefix.
"""
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from sqlalchemy import text
import structlog

logger = structlog.get_logger()

# Paths that require bridge trust verification
BRIDGE_PATHS = (
    "/api/v1/connectors/register",
    "/api/v1/connectors/heartbeat",
)

# Paths exempt from bridge trust (activation uses code-based auth)
EXEMPT_PATHS = (
    "/api/v1/connectors/activate",
    "/api/v1/connectors/activation-codes",
)


class BridgeTrustMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Only verify bridge-specific endpoints
        if not self._is_bridge_path(path):
            return await call_next(request)

        # Skip exempt paths
        for exempt in EXEMPT_PATHS:
            if path.startswith(exempt):
                return await call_next(request)

        # Extract fingerprint from header (set by TLS terminator or bridge itself)
        fingerprint = request.headers.get("X-Client-Cert-Fingerprint", "")

        if not fingerprint:
            # In development, allow pass-through if no cert infrastructure
            import os
            if os.getenv("NEURANAC_BRIDGE_TRUST_ENFORCE", "false").lower() != "true":
                return await call_next(request)

            return JSONResponse(
                status_code=403,
                content={"error": "Missing client certificate fingerprint",
                         "detail": "Bridge must present X-Client-Cert-Fingerprint header"},
            )

        # Look up fingerprint in trust store
        try:
            from app.database.session import get_async_session
            async with get_async_session() as db:
                result = await db.execute(text(
                    "SELECT ct.tenant_id, ct.connector_id, ct.trust_status, ct.expires_at, "
                    "c.status as connector_status "
                    "FROM neuranac_connector_trust ct "
                    "JOIN neuranac_connectors c ON ct.connector_id = c.id "
                    "WHERE ct.fingerprint = :fp"
                ), {"fp": fingerprint})
                row = result.fetchone()

            if not row:
                logger.warning("Unknown certificate fingerprint",
                               fingerprint=fingerprint[:16])
                return JSONResponse(
                    status_code=403,
                    content={"error": "Unknown client certificate"},
                )

            tenant_id, connector_id, trust_status, expires_at, connector_status = row

            if trust_status == "revoked":
                logger.warning("Revoked certificate used",
                               fingerprint=fingerprint[:16], connector_id=str(connector_id))
                return JSONResponse(
                    status_code=403,
                    content={"error": "Client certificate has been revoked"},
                )

            if trust_status != "trusted":
                return JSONResponse(
                    status_code=403,
                    content={"error": f"Certificate status: {trust_status}"},
                )

            # Check expiry
            if expires_at:
                from datetime import datetime, timezone
                if expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
                    logger.warning("Expired certificate used",
                                   fingerprint=fingerprint[:16])
                    return JSONResponse(
                        status_code=403,
                        content={"error": "Client certificate has expired"},
                    )

            # Set trust context on request
            request.state.bridge_tenant_id = str(tenant_id)
            request.state.bridge_connector_id = str(connector_id)
            request.state.bridge_fingerprint = fingerprint

            # Also set tenant_id for downstream tenant scoping
            if not getattr(request.state, "tenant_id", None):
                request.state.tenant_id = str(tenant_id)

            logger.debug("Bridge trust verified",
                         connector_id=str(connector_id),
                         tenant_id=str(tenant_id))

        except Exception as e:
            logger.error("Bridge trust verification failed", error=str(e))
            # In case of DB error, fail open in dev, fail closed in prod
            import os
            if os.getenv("NEURANAC_BRIDGE_TRUST_ENFORCE", "false").lower() == "true":
                return JSONResponse(
                    status_code=500,
                    content={"error": "Trust verification unavailable"},
                )

        return await call_next(request)

    @staticmethod
    def _is_bridge_path(path: str) -> bool:
        """Check if path is a bridge-specific endpoint."""
        for prefix in BRIDGE_PATHS:
            if path.startswith(prefix):
                return True
        # Also check heartbeat pattern: /api/v1/connectors/{id}/heartbeat
        if "/connectors/" in path and path.endswith("/heartbeat"):
            return True
        return False
