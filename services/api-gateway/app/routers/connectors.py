"""Bridge / Connector Management Router — register, heartbeat, status.

The NeuraNAC Bridge service (on-prem or cloud) calls these endpoints to register
itself and send heartbeats. Supports multiple adapter types: NeuraNAC-to-NeuraNAC,
generic REST, and any future adapters.
"""
import json
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
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

class ConnectorRegister(BaseModel):
    site_id: str
    name: Optional[str] = None
    connector_name: Optional[str] = None
    connector_type: str = "bridge"  # "bridge", "neuranac_to_neuranac"
    adapter_type: Optional[str] = None  # specific adapter: "neuranac_to_neuranac", "generic_rest"
    version: Optional[str] = None
    metadata: dict = {}
    legacy_nac_hostname: Optional[str] = None
    legacy_nac_ers_port: Optional[int] = None
    legacy_nac_event_stream_port: Optional[int] = None


class ConnectorHeartbeat(BaseModel):
    status: str = "connected"
    tunnel_status: str = "open"
    tunnel_latency_ms: Optional[int] = None
    events_relayed: Optional[int] = None
    errors_count: Optional[int] = None


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.get("/")
async def list_connectors(request: Request, db: AsyncSession = Depends(get_db)):
    """List all registered connectors for the current tenant."""
    tid = get_tenant_id(request)
    result = await db.execute(text(
        "SELECT c.id, c.site_id, c.connector_type, c.name, c.status, "
        "c.legacy_nac_hostname, c.legacy_nac_ers_port, c.legacy_nac_event_stream_port, "
        "c.tunnel_status, c.tunnel_latency_ms, c.last_heartbeat, "
        "c.events_relayed, c.errors_count, c.version, c.created_at, "
        "s.site_name as site_name, s.site_type "
        "FROM neuranac_connectors c JOIN neuranac_sites s ON c.site_id = s.id "
        "WHERE c.tenant_id = :tid "
        "ORDER BY c.created_at"
    ), {"tid": tid})
    rows = result.fetchall()
    items = []
    for r in rows:
        items.append({
            "id": str(r[0]),
            "site_id": str(r[1]),
            "connector_type": r[2],
            "name": r[3],
            "status": r[4],
            "legacy_nac_hostname": r[5],
            "legacy_nac_ers_port": r[6],
            "legacy_nac_event_stream_port": r[7],
            "tunnel_status": r[8],
            "tunnel_latency_ms": r[9],
            "last_heartbeat": r[10].isoformat() if r[10] else None,
            "events_relayed": r[11],
            "errors_count": r[12],
            "version": r[13],
            "created_at": r[14].isoformat() if r[14] else None,
            "site_name": r[15],
            "site_type": r[16],
        })
    return {"items": items, "total": len(items)}


@router.post("/register", status_code=201)
async def register_connector(body: ConnectorRegister, request: Request, db: AsyncSession = Depends(get_db)):
    """Called by NeuraNAC Bridge on startup to register with the cloud NeuraNAC."""
    tid = get_tenant_id(request)

    # Verify site exists — for bridge registration, resolve tenant from the site
    site_check = await db.execute(
        text("SELECT id, tenant_id FROM neuranac_sites WHERE id = :sid"),
        {"sid": body.site_id},
    )
    site_row = site_check.fetchone()
    if not site_row:
        raise HTTPException(status_code=404, detail=f"Site {body.site_id} not found")
    # Use the site's tenant_id (bridge may not have JWT auth)
    tid = str(site_row[1]) if site_row[1] else tid

    # Quota check
    quota = await db.execute(text(
        "SELECT q.max_connectors, (SELECT count(*) FROM neuranac_connectors WHERE tenant_id = :tid) "
        "FROM neuranac_tenant_quotas q WHERE q.tenant_id = :tid"
    ), {"tid": tid})
    q_row = quota.fetchone()
    if q_row and q_row[1] >= q_row[0]:
        raise HTTPException(status_code=429, detail=f"Connector quota reached ({q_row[0]})")

    result = await db.execute(text(
        "INSERT INTO neuranac_connectors (tenant_id, site_id, connector_type, name, legacy_nac_hostname, "
        "legacy_nac_ers_port, legacy_nac_event_stream_port, version, metadata, status, last_heartbeat) "
        "VALUES (:tid, :sid, :ct, :name, :host, :ers, :evt, :ver, :meta, 'registering', now()) "
        "RETURNING id"
    ), {
        "tid": tid,
        "sid": body.site_id,
        "ct": body.connector_type,
        "name": body.name or body.connector_name or "unnamed",
        "host": body.legacy_nac_hostname,
        "ers": body.legacy_nac_ers_port,
        "evt": body.legacy_nac_event_stream_port,
        "ver": body.version,
        "meta": json.dumps(body.metadata) if body.metadata else "{}",
    })
    await db.commit()
    row = result.fetchone()
    logger.info("Connector registered", connector_id=str(row[0]), name=body.name,
                connector_type=body.connector_type)
    return {"id": str(row[0]), "status": "registered", "name": body.name}


@router.post("/{connector_id}/heartbeat")
async def connector_heartbeat(connector_id: str, body: ConnectorHeartbeat, db: AsyncSession = Depends(get_db)):
    """Called periodically by Bridge Connector to report health."""
    result = await db.execute(text(
        "UPDATE neuranac_connectors SET status = :status, tunnel_status = :ts, "
        "tunnel_latency_ms = :lat, events_relayed = COALESCE(:er, events_relayed), "
        "errors_count = COALESCE(:ec, errors_count), last_heartbeat = now(), "
        "updated_at = now() WHERE id = :cid RETURNING id"
    ), {
        "cid": connector_id,
        "status": body.status,
        "ts": body.tunnel_status,
        "lat": body.tunnel_latency_ms,
        "er": body.events_relayed,
        "ec": body.errors_count,
    })
    await db.commit()
    if not result.fetchone():
        raise HTTPException(status_code=404, detail="Connector not found")
    return {"id": connector_id, "status": "heartbeat_accepted"}


@router.get("/{connector_id}")
async def get_connector(connector_id: str, db: AsyncSession = Depends(get_db)):
    """Get a specific connector by ID."""
    result = await db.execute(text(
        "SELECT c.id, c.site_id, c.connector_type, c.name, c.status, c.legacy_nac_hostname, "
        "c.tunnel_status, c.tunnel_latency_ms, c.last_heartbeat, "
        "c.events_relayed, c.errors_count, c.version, c.created_at, "
        "s.site_name as site_name, s.site_type "
        "FROM neuranac_connectors c JOIN neuranac_sites s ON c.site_id = s.id "
        "WHERE c.id = :cid"
    ), {"cid": connector_id})
    r = result.fetchone()
    if not r:
        raise HTTPException(status_code=404, detail="Connector not found")
    return {
        "id": str(r[0]), "site_id": str(r[1]), "connector_type": r[2],
        "name": r[3], "status": r[4], "legacy_nac_hostname": r[5],
        "tunnel_status": r[6], "tunnel_latency_ms": r[7],
        "last_heartbeat": r[8].isoformat() if r[8] else None,
        "events_relayed": r[9], "errors_count": r[10], "version": r[11],
        "created_at": r[12].isoformat() if r[12] else None,
        "site_name": r[13], "site_type": r[14],
    }


@router.get("/{connector_id}/status")
async def connector_status(connector_id: str, db: AsyncSession = Depends(get_db)):
    """Get detailed status of a specific connector."""
    result = await db.execute(text(
        "SELECT c.id, c.site_id, c.name, c.status, c.legacy_nac_hostname, "
        "c.tunnel_status, c.tunnel_latency_ms, c.last_heartbeat, "
        "c.events_relayed, c.errors_count, c.version, "
        "s.site_name as site_name "
        "FROM neuranac_connectors c JOIN neuranac_sites s ON c.site_id = s.id "
        "WHERE c.id = :cid"
    ), {"cid": connector_id})
    r = result.fetchone()
    if not r:
        raise HTTPException(status_code=404, detail="Connector not found")

    # Calculate health from heartbeat age
    health = "unknown"
    if r[7]:  # last_heartbeat
        age_secs = (datetime.now(timezone.utc).replace(tzinfo=None) - r[7].replace(tzinfo=None)).total_seconds()
        if age_secs < 60:
            health = "healthy"
        elif age_secs < 300:
            health = "degraded"
        else:
            health = "stale"

    return {
        "id": str(r[0]),
        "site_id": str(r[1]),
        "name": r[2],
        "status": r[3],
        "legacy_nac_hostname": r[4],
        "tunnel_status": r[5],
        "tunnel_latency_ms": r[6],
        "last_heartbeat": r[7].isoformat() if r[7] else None,
        "events_relayed": r[8],
        "errors_count": r[9],
        "version": r[10],
        "site_name": r[11],
        "health": health,
    }


@router.delete("/{connector_id}")
async def deregister_connector(connector_id: str, db: AsyncSession = Depends(get_db)):
    """Remove a connector registration."""
    result = await db.execute(
        text("DELETE FROM neuranac_connectors WHERE id = :cid RETURNING id"),
        {"cid": connector_id},
    )
    await db.commit()
    if not result.fetchone():
        raise HTTPException(status_code=404, detail="Connector not found")
    logger.info("Connector deregistered", connector_id=connector_id)
    return {"id": connector_id, "status": "deregistered"}
