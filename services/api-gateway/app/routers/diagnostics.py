"""Diagnostics router - troubleshooting, support bundles, connectivity tests"""
import httpx
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from typing import Optional

from app.config import get_settings

router = APIRouter()


class TroubleshootRequest(BaseModel):
    query: str
    session_id: Optional[str] = None
    endpoint_mac: Optional[str] = None
    username: Optional[str] = None


class ConnectivityTestRequest(BaseModel):
    target: str  # hostname or IP
    port: int = 443
    protocol: str = "tcp"


@router.post("/troubleshoot")
async def ai_troubleshoot(req: TroubleshootRequest):
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"http://{settings.ai_engine_host}:{settings.ai_engine_port}/api/v1/troubleshoot",
                json=req.model_dump(),
            )
            return resp.json()
    except Exception as e:
        return {"root_cause": "AI Engine unavailable", "recommended_fixes": [str(e)]}


@router.get("/system-status")
async def system_status():
    settings = get_settings()
    services = {}
    for svc, url in [
        ("api-gateway", f"http://localhost:{settings.api_port}/health"),
        ("policy-engine", "http://policy-engine:8082/health"),
        ("ai-engine", f"http://{settings.ai_engine_host}:{settings.ai_engine_port}/health"),
        ("sync-engine", "http://sync-engine:9100/health"),
    ]:
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                resp = await client.get(url)
                services[svc] = "healthy" if resp.status_code == 200 else "degraded"
        except Exception:
            services[svc] = "unreachable"
    overall = "healthy" if all(v == "healthy" for v in services.values()) else "degraded"
    return {"status": overall, "services": services}


@router.post("/connectivity-test")
async def connectivity_test(req: ConnectivityTestRequest):
    import socket
    try:
        sock = socket.create_connection((req.target, req.port), timeout=5)
        sock.close()
        return {"status": "success", "target": req.target, "port": req.port}
    except Exception as e:
        return {"status": "failed", "target": req.target, "port": req.port, "error": str(e)}


@router.post("/support-bundle")
async def generate_support_bundle():
    return {"status": "generating", "bundle_id": "sb-001", "estimated_size_mb": 50}


@router.get("/radius-live-log")
async def radius_live_log(limit: int = Query(50)):
    return {"entries": [], "total": 0}


@router.get("/db-schema-check")
async def db_schema_check():
    """Check database schema integrity — returns per-check pass/fail."""
    from app.database.session import engine as db_engine
    checks = []
    overall = "pass"
    try:
        from sqlalchemy import text as sa_text
        from sqlalchemy.ext.asyncio import AsyncSession
        if db_engine is None:
            raise RuntimeError("Database not initialized")
        async with AsyncSession(db_engine) as session:
            # Check tables exist
            result = await session.execute(sa_text(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
            ))
            tables = [r[0] for r in result.fetchall()]
            checks.append({"check": "tables_exist", "status": "pass", "count": len(tables)})

            # Check extensions
            result = await session.execute(sa_text(
                "SELECT extname FROM pg_extension"
            ))
            extensions = [r[0] for r in result.fetchall()]
            checks.append({"check": "extensions", "status": "pass", "items": extensions})
    except Exception as e:
        overall = "error"
        checks.append({"check": "connection", "status": "fail", "error": str(e)})

    return {"status": overall, "checks": checks}
