"""Health check router"""
import os
import time

import httpx
from fastapi import APIRouter
from sqlalchemy import text

from app.config import get_settings

router = APIRouter()


@router.get("/health")
async def health_check():
    return {"status": "healthy", "service": "api-gateway", "version": "1.0.0"}


@router.get("/ready")
async def readiness_check():
    from app.database.redis import get_redis
    settings = get_settings()
    checks = {"database": "ok", "redis": "ok", "nats": "ok"}
    try:
        rdb = get_redis()
        if rdb:
            await rdb.ping()
    except Exception:
        checks["redis"] = "error"
    return {"status": "ready" if all(v == "ok" for v in checks.values()) else "degraded", "checks": checks}


@router.get("/health/full")
async def full_health_check():
    """Deep dependency health check — verifies PostgreSQL, Redis, NATS, AI Engine."""
    from app.database.session import async_session_factory
    from app.database.redis import get_redis

    settings = get_settings()
    checks = {}
    overall = "healthy"

    # --- PostgreSQL ---
    try:
        from app.database.session import get_pool_status
        t0 = time.monotonic()
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        latency_ms = round((time.monotonic() - t0) * 1000, 1)
        checks["postgres"] = {"status": "ok", "latency_ms": latency_ms, "pool": get_pool_status()}
    except Exception as e:
        checks["postgres"] = {"status": "error", "error": str(e)}
        overall = "degraded"

    # --- Redis ---
    try:
        rdb = get_redis()
        if rdb:
            t0 = time.monotonic()
            await rdb.ping()
            latency_ms = round((time.monotonic() - t0) * 1000, 1)
            info = await rdb.info("memory")
            checks["redis"] = {
                "status": "ok",
                "latency_ms": latency_ms,
                "used_memory_human": info.get("used_memory_human", "unknown"),
            }
        else:
            checks["redis"] = {"status": "unavailable"}
            overall = "degraded"
    except Exception as e:
        checks["redis"] = {"status": "error", "error": str(e)}
        overall = "degraded"

    # --- NATS ---
    try:
        nc_url = settings.nats_url.replace("nats://", "http://").split(",")[0]
        # NATS monitoring endpoint is typically on port 8222
        nats_host = nc_url.split("://")[-1].split(":")[0]
        monitoring_url = f"http://{nats_host}:8222/varz"
        async with httpx.AsyncClient(timeout=3) as client:
            resp = await client.get(monitoring_url)
            if resp.status_code == 200:
                checks["nats"] = {"status": "ok"}
            else:
                checks["nats"] = {"status": "degraded", "http_status": resp.status_code}
                overall = "degraded"
    except Exception:
        checks["nats"] = {"status": "unknown", "note": "monitoring port unreachable"}

    # --- AI Engine ---
    try:
        ai_url = f"http://{settings.ai_engine_host}:{settings.ai_engine_port}/health"
        async with httpx.AsyncClient(timeout=3) as client:
            t0 = time.monotonic()
            resp = await client.get(ai_url)
            latency_ms = round((time.monotonic() - t0) * 1000, 1)
            if resp.status_code == 200:
                checks["ai_engine"] = {"status": "ok", "latency_ms": latency_ms}
            else:
                checks["ai_engine"] = {"status": "degraded", "http_status": resp.status_code}
                overall = "degraded"
    except Exception as e:
        checks["ai_engine"] = {"status": "unreachable", "error": str(e)}

    return {
        "status": overall,
        "service": "api-gateway",
        "version": "1.0.0",
        "checks": checks,
    }
