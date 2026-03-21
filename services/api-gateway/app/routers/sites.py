"""Site Management Router — CRUD for NeuraNAC sites (on-prem, cloud, hybrid pairs).

Works in all 4 deployment scenarios:
  - standalone: shows 1 site (self)
  - hybrid: shows 2 sites (self + peer) with health and sync status
"""
import httpx
from datetime import datetime, timezone
from typing import Optional, List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import structlog

from app.config import get_settings
from app.database.session import get_db
from app.middleware.tenant_helper import get_tenant_id

logger = structlog.get_logger()
router = APIRouter()


# ─── Models ──────────────────────────────────────────────────────────────────

class SiteCreate(BaseModel):
    name: str
    site_type: str = Field(..., pattern="^(onprem|cloud)$")
    deployment_mode: str = Field(default="standalone", pattern="^(standalone|hybrid)$")
    api_url: Optional[str] = None
    peer_site_id: Optional[str] = None
    region: Optional[str] = None
    description: Optional[str] = None


class SiteUpdate(BaseModel):
    name: Optional[str] = None
    api_url: Optional[str] = None
    peer_site_id: Optional[str] = None
    region: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.get("/")
async def list_sites(request: Request, db: AsyncSession = Depends(get_db)):
    """List all registered sites for the current tenant."""
    tid = get_tenant_id(request)
    result = await db.execute(text(
        "SELECT id, site_name, site_type, deployment_mode, api_url, peer_site_id, "
        "region, description, status, last_heartbeat_at, created_at, updated_at "
        "FROM neuranac_sites WHERE tenant_id = :tid ORDER BY created_at"
    ), {"tid": tid})
    rows = result.fetchall()
    settings = get_settings()
    items = []
    for r in rows:
        items.append({
            "id": str(r[0]),
            "name": r[1],
            "site_type": r[2],
            "deployment_mode": r[3],
            "api_url": r[4],
            "peer_site_id": str(r[5]) if r[5] else None,
            "region": r[6],
            "description": r[7],
            "status": r[8],
            "last_heartbeat": r[9].isoformat() if r[9] else None,
            "is_self": str(r[0]) == settings.neuranac_site_id,
            "created_at": r[10].isoformat() if r[10] else None,
            "updated_at": r[11].isoformat() if r[11] else None,
        })
    return {"items": items, "total": len(items), "deployment_mode": settings.deployment_mode}


@router.get("/{site_id}")
async def get_site(site_id: str, db: AsyncSession = Depends(get_db)):
    """Get a specific site by ID."""
    result = await db.execute(text(
        "SELECT id, site_name, site_type, deployment_mode, api_url, peer_site_id, "
        "region, description, status, last_heartbeat_at, created_at, updated_at "
        "FROM neuranac_sites WHERE id = :sid"
    ), {"sid": site_id})
    r = result.fetchone()
    if not r:
        raise HTTPException(status_code=404, detail="Site not found")
    settings = get_settings()
    return {
        "id": str(r[0]),
        "name": r[1],
        "site_type": r[2],
        "deployment_mode": r[3],
        "api_url": r[4],
        "peer_site_id": str(r[5]) if r[5] else None,
        "region": r[6],
        "description": r[7],
        "status": r[8],
        "last_heartbeat": r[9].isoformat() if r[9] else None,
        "is_self": str(r[0]) == settings.neuranac_site_id,
        "created_at": r[10].isoformat() if r[10] else None,
        "updated_at": r[11].isoformat() if r[11] else None,
    }


@router.post("/", status_code=201)
async def create_site(site: SiteCreate, request: Request, db: AsyncSession = Depends(get_db)):
    """Register a new site for the current tenant."""
    tid = get_tenant_id(request)
    # Quota check
    quota = await db.execute(text(
        "SELECT q.max_sites, (SELECT count(*) FROM neuranac_sites WHERE tenant_id = :tid) "
        "FROM neuranac_tenant_quotas q WHERE q.tenant_id = :tid"
    ), {"tid": tid})
    q_row = quota.fetchone()
    if q_row and q_row[1] >= q_row[0]:
        raise HTTPException(status_code=429, detail=f"Site quota reached ({q_row[0]})")

    result = await db.execute(text(
        "INSERT INTO neuranac_sites (tenant_id, site_name, site_type, node_id, deployment_mode, api_url, peer_site_id, region, description) "
        "VALUES (:tid, :name, :st, 'node-' || left(gen_random_uuid()::text, 8), :dm, :url, :peer, :region, :desc) RETURNING id"
    ), {
        "tid": tid,
        "name": site.name,
        "st": site.site_type,
        "dm": site.deployment_mode,
        "url": site.api_url,
        "peer": site.peer_site_id,
        "region": site.region,
        "desc": site.description,
    })
    await db.commit()
    row = result.fetchone()
    return {"id": str(row[0]), "name": site.name, "status": "created"}


@router.put("/{site_id}")
async def update_site(site_id: str, site: SiteUpdate, db: AsyncSession = Depends(get_db)):
    """Update a site's configuration."""
    sets = []
    params = {"sid": site_id}
    field_map = {"name": "site_name", "api_url": "api_url", "peer_site_id": "peer_site_id", "region": "region", "description": "description", "status": "status"}
    for field in ("name", "api_url", "peer_site_id", "region", "description", "status"):
        val = getattr(site, field, None)
        if val is not None:
            col = field_map.get(field, field)
            sets.append(f"{col} = :{field}")
            params[field] = val
    if not sets:
        raise HTTPException(status_code=400, detail="No fields to update")
    sets.append("updated_at = now()")
    query = f"UPDATE neuranac_sites SET {', '.join(sets)} WHERE id = :sid RETURNING id"
    result = await db.execute(text(query), params)
    await db.commit()
    if not result.fetchone():
        raise HTTPException(status_code=404, detail="Site not found")
    return {"id": site_id, "status": "updated"}


@router.delete("/{site_id}")
async def delete_site(site_id: str, db: AsyncSession = Depends(get_db)):
    """Remove a site registration."""
    settings = get_settings()
    if site_id == settings.neuranac_site_id:
        raise HTTPException(status_code=400, detail="Cannot delete self site")
    result = await db.execute(
        text("DELETE FROM neuranac_sites WHERE id = :sid RETURNING id"),
        {"sid": site_id},
    )
    await db.commit()
    if not result.fetchone():
        raise HTTPException(status_code=404, detail="Site not found")
    return {"id": site_id, "status": "deleted"}


@router.get("/{site_id}/health")
async def site_health(site_id: str, db: AsyncSession = Depends(get_db)):
    """Check health of a site. For peer sites, probes the remote API."""
    settings = get_settings()

    # Self site — always healthy if we're responding
    if site_id == settings.neuranac_site_id:
        await db.execute(
            text("UPDATE neuranac_sites SET last_heartbeat = now(), status = 'active' WHERE id = :sid"),
            {"sid": site_id},
        )
        await db.commit()
        return {"site_id": site_id, "status": "healthy", "is_self": True}

    # Peer site — probe remote API
    result = await db.execute(
        text("SELECT api_url FROM neuranac_sites WHERE id = :sid"),
        {"sid": site_id},
    )
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Site not found")

    api_url = row[0]
    if not api_url:
        return {"site_id": site_id, "status": "unknown", "error": "No API URL configured"}

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{api_url}/health")
            healthy = resp.status_code == 200
            status = "healthy" if healthy else "degraded"
            await db.execute(
                text("UPDATE neuranac_sites SET last_heartbeat = now(), status = :s WHERE id = :sid"),
                {"s": "active" if healthy else "degraded", "sid": site_id},
            )
            await db.commit()
            return {"site_id": site_id, "status": status, "is_self": False, "response_code": resp.status_code}
    except Exception as e:
        await db.execute(
            text("UPDATE neuranac_sites SET status = 'unreachable' WHERE id = :sid"),
            {"sid": site_id},
        )
        await db.commit()
        return {"site_id": site_id, "status": "unreachable", "error": str(e)}


@router.get("/peer/status")
async def peer_status(db: AsyncSession = Depends(get_db)):
    """Quick check: is the peer site reachable? Returns 'no_peer' in standalone mode."""
    settings = get_settings()
    if settings.deployment_mode != "hybrid" or not settings.neuranac_peer_api_url:
        return {"deployment_mode": settings.deployment_mode, "peer_status": "no_peer"}

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.get(f"{settings.neuranac_peer_api_url}/health")
            return {
                "deployment_mode": "hybrid",
                "peer_status": "healthy" if resp.status_code == 200 else "degraded",
                "peer_url": settings.neuranac_peer_api_url,
                "response_code": resp.status_code,
            }
    except Exception as e:
        return {
            "deployment_mode": "hybrid",
            "peer_status": "unreachable",
            "peer_url": settings.neuranac_peer_api_url,
            "error": str(e),
        }
