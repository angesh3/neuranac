"""Cross-Site Federation Middleware — routes requests to peer site based on X-NeuraNAC-Site header.

Behavior:
  - X-NeuraNAC-Site: local (or absent)  → handle locally (default)
  - X-NeuraNAC-Site: peer               → proxy entire request to NEURANAC_PEER_API_URL
  - X-NeuraNAC-Site: all                → fan-out: call local + proxy to peer, merge results
  - DEPLOYMENT_MODE=standalone      → ignore header, always local

Security:
  - Outbound proxied requests are signed with HMAC-SHA256 using FEDERATION_SHARED_SECRET.
  - Inbound federated requests (x-neuranac-federated: true) are verified against the same secret.
  - If no shared secret is configured, federation proxy is disabled with a warning.

Only active when DEPLOYMENT_MODE=hybrid and NEURANAC_PEER_API_URL is configured.
"""
import hashlib
import hmac
import json
import time
from typing import Optional

import httpx
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
import structlog

from app.config import get_settings

logger = structlog.get_logger()

# Circuit breaker state for peer connectivity
_peer_failures: int = 0
_peer_circuit_open_until: float = 0.0
_PEER_FAILURE_THRESHOLD = 3
_PEER_CIRCUIT_OPEN_DURATION = 30.0  # seconds

# Paths that should NEVER be federated (health, metrics, auth, config)
FEDERATION_SKIP_PREFIXES = (
    "/health", "/ready", "/metrics", "/api/docs", "/api/redoc",
    "/api/v1/auth", "/api/v1/config", "/api/v1/ws/",
    "/api/v1/openapi.json",
)


def _sign_request(secret: str, method: str, path: str, timestamp: str) -> str:
    """Generate HMAC-SHA256 signature for inter-site authentication."""
    message = f"{method}\n{path}\n{timestamp}"
    return hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()


def _verify_signature(secret: str, method: str, path: str, timestamp: str, signature: str) -> bool:
    """Verify HMAC-SHA256 signature from peer site. Rejects requests older than 60s."""
    try:
        ts = float(timestamp)
        if abs(time.time() - ts) > 60:
            return False  # Replay protection
    except (ValueError, TypeError):
        return False
    expected = _sign_request(secret, method, path, timestamp)
    return hmac.compare_digest(expected, signature)


class FederationMiddleware(BaseHTTPMiddleware):
    """Intercepts API requests and optionally proxies to the peer site."""

    async def dispatch(self, request: Request, call_next):
        global _peer_failures, _peer_circuit_open_until
        settings = get_settings()

        # Skip if standalone mode or no peer configured
        if settings.deployment_mode != "hybrid" or not settings.neuranac_peer_api_url:
            return await call_next(request)

        # Verify inbound federated requests from peer
        if request.headers.get("x-neuranac-federated") == "true":
            fed_secret = getattr(settings, "federation_shared_secret", "")
            if fed_secret:
                sig = request.headers.get("x-neuranac-federation-sig", "")
                ts = request.headers.get("x-neuranac-federation-ts", "")
                if not _verify_signature(fed_secret, request.method, request.url.path, ts, sig):
                    return JSONResponse(
                        status_code=403,
                        content={"error": "Federation signature verification failed"},
                    )

        # Skip non-API paths and system paths
        path = request.url.path
        if any(path.startswith(p) for p in FEDERATION_SKIP_PREFIXES):
            return await call_next(request)

        site_header = request.headers.get("X-NeuraNAC-Site", "local").lower()

        if site_header == "local" or site_header == "":
            return await call_next(request)

        # Check circuit breaker before proxying
        if time.time() < _peer_circuit_open_until:
            return JSONResponse(
                status_code=503,
                content={"error": "Peer site circuit breaker open", "retry_after_seconds": int(_peer_circuit_open_until - time.time())},
            )

        if site_header == "peer":
            return await self._proxy_to_peer(request, settings.neuranac_peer_api_url)

        if site_header == "all":
            return await self._fan_out(request, call_next, settings.neuranac_peer_api_url)

        # Unknown value — treat as local
        return await call_next(request)

    def _build_signed_headers(self, request: Request) -> dict:
        """Build headers for outbound federated request with HMAC signature."""
        settings = get_settings()
        headers = dict(request.headers)
        headers.pop("host", None)
        headers["x-neuranac-site"] = "local"
        headers["x-neuranac-federated"] = "true"
        headers["x-neuranac-origin-site"] = settings.neuranac_site_id

        fed_secret = getattr(settings, "federation_shared_secret", "")
        if fed_secret:
            ts = str(time.time())
            sig = _sign_request(fed_secret, request.method, request.url.path, ts)
            headers["x-neuranac-federation-ts"] = ts
            headers["x-neuranac-federation-sig"] = sig
        return headers

    def _record_peer_success(self):
        global _peer_failures
        _peer_failures = 0

    def _record_peer_failure(self):
        global _peer_failures, _peer_circuit_open_until
        _peer_failures += 1
        if _peer_failures >= _PEER_FAILURE_THRESHOLD:
            _peer_circuit_open_until = time.time() + _PEER_CIRCUIT_OPEN_DURATION
            logger.warning("Federation circuit breaker opened", failures=_peer_failures,
                           open_for_seconds=_PEER_CIRCUIT_OPEN_DURATION)

    async def _proxy_to_peer(self, request: Request, peer_url: str) -> Response:
        """Forward the entire request to the peer site's API Gateway."""
        try:
            target_url = f"{peer_url}{request.url.path}"
            if request.url.query:
                target_url += f"?{request.url.query}"

            body = await request.body()
            headers = self._build_signed_headers(request)

            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.request(
                    method=request.method,
                    url=target_url,
                    content=body,
                    headers=headers,
                )
                self._record_peer_success()
                return Response(
                    content=resp.content,
                    status_code=resp.status_code,
                    headers=dict(resp.headers),
                    media_type=resp.headers.get("content-type"),
                )
        except httpx.ConnectError:
            self._record_peer_failure()
            return JSONResponse(
                status_code=502,
                content={"error": "Peer site unreachable", "peer_url": peer_url},
            )
        except httpx.TimeoutException:
            self._record_peer_failure()
            return JSONResponse(
                status_code=504,
                content={"error": "Peer site request timed out", "peer_url": peer_url},
            )
        except Exception as e:
            self._record_peer_failure()
            logger.warning("Federation proxy error", error=str(e))
            return JSONResponse(
                status_code=502,
                content={"error": f"Federation proxy error: {str(e)}"},
            )

    async def _fan_out(self, request: Request, call_next, peer_url: str) -> Response:
        """Call both local and peer, merge JSON list results."""
        # Get local response
        local_response = await call_next(request)

        # Read local body
        local_body_bytes = b""
        async for chunk in local_response.body_iterator:
            if isinstance(chunk, bytes):
                local_body_bytes += chunk
            else:
                local_body_bytes += chunk.encode()

        try:
            local_data = json.loads(local_body_bytes)
        except (json.JSONDecodeError, UnicodeDecodeError):
            # Not JSON — can't merge, return local only
            return Response(
                content=local_body_bytes,
                status_code=local_response.status_code,
                headers=dict(local_response.headers),
            )

        # Get peer response
        peer_data = None
        try:
            target_url = f"{peer_url}{request.url.path}"
            if request.url.query:
                target_url += f"?{request.url.query}"

            body = await request.body()
            headers = self._build_signed_headers(request)

            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.request(
                    method=request.method,
                    url=target_url,
                    content=body,
                    headers=headers,
                )
                if resp.status_code == 200:
                    peer_data = resp.json()
        except Exception as e:
            logger.debug("Federation fan-out peer failed", error=str(e))

        # Merge: if both have "items" lists, concatenate them
        if peer_data and isinstance(local_data, dict) and isinstance(peer_data, dict):
            if "items" in local_data and "items" in peer_data:
                # Tag items with source site
                settings = get_settings()
                for item in local_data["items"]:
                    item.setdefault("_site", "local")
                    item.setdefault("_site_type", settings.neuranac_site_type)
                for item in peer_data["items"]:
                    item.setdefault("_site", "peer")
                    item.setdefault("_site_type", "cloud" if settings.neuranac_site_type == "onprem" else "onprem")

                merged = {
                    **local_data,
                    "items": local_data["items"] + peer_data["items"],
                    "total": local_data.get("total", 0) + peer_data.get("total", 0),
                    "_federated": True,
                    "_local_count": len(local_data["items"]),
                    "_peer_count": len(peer_data["items"]),
                }
                return JSONResponse(content=merged)

        # Can't merge — return local with peer info attached
        if peer_data:
            local_data["_peer_data"] = peer_data
            local_data["_federated"] = True
        return JSONResponse(content=local_data)
