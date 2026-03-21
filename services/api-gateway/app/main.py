"""NeuraNAC API Gateway - FastAPI Application"""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import structlog

from app.database.session import init_db, close_db
from app.database.redis import init_redis, close_redis
from app.services.nats_client import init_nats, close_nats
from app.services.telemetry_consumer import start_telemetry_consumer, stop_telemetry_consumer
from app.middleware.tenant import TenantMiddleware
from app.middleware.auth import AuthMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.security import SecurityHeadersMiddleware
from app.middleware.metrics import PrometheusMetricsMiddleware, get_metrics_text
from app.middleware.validation import InputValidationMiddleware
from app.middleware.tracing import OTelTracingMiddleware
from app.middleware.log_correlation import LogCorrelationMiddleware
from app.middleware.api_key import APIKeyMiddleware
from app.middleware.bridge_trust import BridgeTrustMiddleware
from app.routers import (
    auth,
    policies,
    network_devices,
    endpoints,
    sessions,
    identity_sources,
    certificates,
    segmentation,
    guest,
    posture,
    ai_agents,
    ai_data_flow,
    ai_chat,
    nodes,
    admin,
    licenses,
    audit,
    setup,
    diagnostics,
    health,
    privacy,
    siem,
    webhooks,
    websocket_events,
    topology,
    ui_config,
    sites,
    connectors,
    activation,
    tenants,
    telemetry,
)
from app.routers import feature_flags
from app.middleware.federation import FederationMiddleware
from app.middleware.waf import WAFMiddleware

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events"""
    logger.info("Starting NeuraNAC API Gateway", version="1.0.0")
    # Validate federation config for hybrid deployments
    from app.config import get_settings
    _settings = get_settings()
    if _settings.deployment_mode == "hybrid":
        if not _settings.federation_shared_secret:
            logger.warning("FEDERATION_SHARED_SECRET is not set — inter-site requests will NOT be authenticated")
        elif len(_settings.federation_shared_secret) < 32:
            logger.warning("FEDERATION_SHARED_SECRET is shorter than 32 chars — consider using a stronger secret")
        if not _settings.neuranac_peer_api_url:
            logger.warning("NEURANAC_PEER_API_URL is not set — federation proxy will be disabled")
    await init_db()
    await init_redis()
    await init_nats()
    # Run bootstrap on first start
    from app.bootstrap import run_bootstrap
    await run_bootstrap()
    # Start NATS → DB telemetry consumer (ingestion-collector events)
    await start_telemetry_consumer()
    yield
    await stop_telemetry_consumer()
    await close_nats()
    await close_db()
    await close_redis()
    logger.info("NeuraNAC API Gateway stopped")


app = FastAPI(
    title="NeuraNAC API",
    description="AI-Aware Hybrid Network Access Control Platform",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/v1/openapi.json",
    lifespan=lifespan,
)

# CORS
cors_origins = os.getenv("API_CORS_ORIGINS", "http://localhost:5173,http://localhost:3001").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-Tenant-ID", "X-NeuraNAC-Site", "Accept"],
    expose_headers=["X-Request-ID", "X-RateLimit-Limit", "X-RateLimit-Remaining", "Retry-After"],
    max_age=600,
)

# Custom middleware (order matters - outermost first)
app.add_middleware(WAFMiddleware)
app.add_middleware(LogCorrelationMiddleware)
app.add_middleware(OTelTracingMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(PrometheusMetricsMiddleware)
app.add_middleware(InputValidationMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(APIKeyMiddleware)
app.add_middleware(AuthMiddleware)
app.add_middleware(BridgeTrustMiddleware)
app.add_middleware(TenantMiddleware)
app.add_middleware(FederationMiddleware)

# Register routers
API_V1 = "/api/v1"
app.include_router(health.router, tags=["Health"])
app.include_router(health.router, prefix=f"{API_V1}", tags=["Health"])
app.include_router(auth.router, prefix=f"{API_V1}/auth", tags=["Authentication"])
app.include_router(setup.router, prefix=f"{API_V1}/setup", tags=["Setup Wizard"])
app.include_router(policies.router, prefix=f"{API_V1}/policies", tags=["Policies"])
app.include_router(network_devices.router, prefix=f"{API_V1}/network-devices", tags=["Network Devices"])
app.include_router(endpoints.router, prefix=f"{API_V1}/endpoints", tags=["Endpoints"])
app.include_router(sessions.router, prefix=f"{API_V1}/sessions", tags=["Sessions"])
app.include_router(identity_sources.router, prefix=f"{API_V1}/identity-sources", tags=["Identity Sources"])
app.include_router(certificates.router, prefix=f"{API_V1}/certificates", tags=["Certificates"])
app.include_router(segmentation.router, prefix=f"{API_V1}/segmentation", tags=["Segmentation"])
app.include_router(guest.router, prefix=f"{API_V1}/guest", tags=["Guest & BYOD"])
app.include_router(posture.router, prefix=f"{API_V1}/posture", tags=["Posture & Compliance"])
app.include_router(ai_agents.router, prefix=f"{API_V1}/ai/agents", tags=["AI Agents"])
app.include_router(ai_data_flow.router, prefix=f"{API_V1}/ai/data-flow", tags=["AI Data Flow"])
app.include_router(ai_chat.router, prefix=f"{API_V1}/ai", tags=["AI Chat"])
app.include_router(nodes.router, prefix=f"{API_V1}/nodes", tags=["Twin Nodes"])
app.include_router(admin.router, prefix=f"{API_V1}/admin", tags=["Administration"])
app.include_router(licenses.router, prefix=f"{API_V1}/licenses", tags=["Licenses"])
app.include_router(audit.router, prefix=f"{API_V1}/audit", tags=["Audit"])
app.include_router(diagnostics.router, prefix=f"{API_V1}/diagnostics", tags=["Diagnostics"])
app.include_router(privacy.router, prefix=f"{API_V1}/privacy", tags=["Privacy & Compliance"])
app.include_router(siem.router, prefix=f"{API_V1}/siem", tags=["SIEM & SOAR Integration"])
app.include_router(webhooks.router, prefix=f"{API_V1}/webhooks", tags=["Webhooks & Plugins"])
app.include_router(websocket_events.router, prefix=f"{API_V1}/ws", tags=["WebSocket Events"])
app.include_router(topology.router, prefix=f"{API_V1}/topology", tags=["Topology"])
app.include_router(ui_config.router, prefix=f"{API_V1}/config", tags=["UI Configuration"])
app.include_router(sites.router, prefix=f"{API_V1}/sites", tags=["Site Management"])
app.include_router(connectors.router, prefix=f"{API_V1}/connectors", tags=["Connectors"])
app.include_router(activation.router, prefix=f"{API_V1}/connectors", tags=["Connector Activation"])
app.include_router(tenants.router, prefix=f"{API_V1}/tenants", tags=["Tenant Management"])
app.include_router(telemetry.router, prefix=f"{API_V1}/telemetry", tags=["Network Telemetry"])
app.include_router(feature_flags.router, prefix=f"{API_V1}/feature-flags", tags=["Feature Flags"])


@app.get("/metrics")
async def prometheus_metrics():
    """Prometheus metrics endpoint"""
    from starlette.responses import PlainTextResponse
    return PlainTextResponse(get_metrics_text(), media_type="text/plain; version=0.0.4")


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail, "status_code": exc.status_code},
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception", error=str(exc), path=request.url.path)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "status_code": 500},
    )
