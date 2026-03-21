"""NeuraNAC Bridge Service — generic connection manager for all site-to-site communication.

Replaces the old NeuraNAC-only connector with a pluggable adapter architecture.
Runs on EVERY site (on-prem AND cloud), not just on-prem with NeuraNAC.

Adapter types:
  - NeuraNAC: ERS API proxy + Event Stream relay (optional, only if NeuraNAC exists)
  - NeuraNAC-to-NeuraNAC: gRPC bidi stream + HTTP proxy + NATS leaf (cross-site)
  - Generic REST: Webhook/SIEM outbound (future)

Lifecycle:
  1. Start → activate (if code) → auto-discover adapters from config
  2. Register with cloud NeuraNAC (POST /api/v1/connectors/register)
  3. Open outbound tunnel to cloud (WebSocket or gRPC)
  4. ConnectionManager spawns adapter instances per connection
  5. Heartbeat every 30s
"""
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
import structlog

from app.config import get_bridge_settings
from app.connection_manager import get_connection_manager
from app.registration import get_registration
from app.tunnel import get_tunnel
from app.routers import health, connections, relay

# Import adapters to trigger registration with ConnectionManager
import app.adapters  # noqa: F401

logger = structlog.get_logger()


async def _try_activation_bootstrap(settings) -> bool:
    """If an activation code is set, call the cloud activate endpoint to auto-configure."""
    if not settings.activation_code:
        return False

    import httpx
    code = settings.activation_code.strip().upper()
    api_url = settings.cloud_neuranac_api_url
    logger.info("Attempting zero-trust activation", code=code[:8] + "****", api_url=api_url)

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{api_url}/api/v1/connectors/activate",
                json={
                    "code": code,
                    "connector_name": settings.bridge_name,
                    "connector_type": "bridge",
                },
            )
            if resp.status_code == 200:
                data = resp.json()
                settings.site_id = data.get("site_id", settings.site_id)
                settings.tenant_id = data.get("tenant_id", settings.tenant_id)
                settings.cloud_neuranac_api_url = data.get("cloud_api_url", settings.cloud_neuranac_api_url)
                settings.cloud_neuranac_ws_url = data.get("cloud_ws_url", settings.cloud_neuranac_ws_url)
                # mTLS certs from activation
                if data.get("client_cert_pem"):
                    logger.info("Received mTLS client certificate from activation")
                logger.info("Zero-trust activation successful",
                            connector_id=data.get("connector_id"),
                            site_id=data.get("site_id"),
                            tenant_id=data.get("tenant_id"))
                return True
            else:
                logger.error("Activation failed",
                             status=resp.status_code, detail=resp.text[:200])
                return False
    except Exception as e:
        logger.error("Activation request failed", error=str(e), api_url=api_url)
        return False


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: activate, discover adapters, register, open tunnel. Shutdown: close all."""
    settings = get_bridge_settings()
    logger.info("Starting NeuraNAC Bridge",
                name=settings.bridge_name,
                site_type=settings.site_type,
                deployment_mode=settings.deployment_mode,
                legacy_nac_enabled=settings.legacy_nac_enabled,
                simulated=settings.simulated,
                enabled_adapters=settings.enabled_adapters)

    # Zero-trust activation bootstrap
    if settings.activation_code:
        activated = await _try_activation_bootstrap(settings)
        if activated:
            logger.info("Bridge auto-configured via activation code")
        else:
            logger.warning("Activation failed — falling back to manual config")

    # Start ConnectionManager (auto-discovers and spawns adapters from config)
    manager = get_connection_manager()
    await manager.start()

    # Start registration + heartbeat loop
    registration = get_registration()
    heartbeat_task = asyncio.create_task(registration.start_heartbeat_loop())

    # Start outbound tunnel to cloud
    tunnel = get_tunnel()
    tunnel_task = asyncio.create_task(tunnel.start())

    logger.info("NeuraNAC Bridge started successfully",
                connections=manager.connection_count)

    yield

    # Shutdown
    logger.info("Shutting down NeuraNAC Bridge")
    await registration.stop()
    await tunnel.stop()
    await manager.stop()
    heartbeat_task.cancel()
    tunnel_task.cancel()
    try:
        await heartbeat_task
    except asyncio.CancelledError:
        pass
    try:
        await tunnel_task
    except asyncio.CancelledError:
        pass
    logger.info("NeuraNAC Bridge stopped")


app = FastAPI(
    title="NeuraNAC Bridge",
    description="Generic connection manager bridging on-prem and cloud NeuraNAC with pluggable adapters",
    version="1.0.0",
    lifespan=lifespan,
)

# Register routers
app.include_router(health.router, tags=["Health"])
app.include_router(connections.router, prefix="/connections", tags=["Connections"])
app.include_router(relay.router, prefix="/relay", tags=["Relay"])
