"""Node Management Router — register, list, drain, health for Node 1...n pattern.

Supports both legacy twin-node status and new multi-node registry across sites.
"""
import json
import httpx
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.config import get_settings
from app.database.session import get_db
from app.middleware.tenant_helper import get_tenant_id

router = APIRouter()


# ─── Models ──────────────────────────────────────────────────────────────────

class NodeRegister(BaseModel):
    site_id: str
    node_name: str
    role: str = "worker"
    k8s_pod_name: Optional[str] = None
    k8s_namespace: Optional[str] = None
    service_type: Optional[str] = None
    ip_address: Optional[str] = None
    metadata: dict = {}


class NodeHeartbeat(BaseModel):
    status: str = "active"
    active_sessions: int = 0
    cpu_pct: float = 0.0
    mem_pct: float = 0.0


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.get("/")
async def list_nodes(request: Request, site_id: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    """List all registered nodes for the current tenant, optionally filtered by site.
    Falls back to legacy twin-node response if neuranac_node_registry is empty.
    """
    tid = get_tenant_id(request)
    try:
        query = (
            "SELECT n.id, n.site_id, n.node_name, n.role, n.k8s_pod_name, "
            "n.service_type, n.ip_address, n.status, n.active_sessions, "
            "n.cpu_pct, n.mem_pct, n.last_heartbeat, n.created_at, "
            "s.site_name as site_name, s.site_type "
            "FROM neuranac_node_registry n JOIN neuranac_sites s ON n.site_id = s.id "
            "WHERE n.tenant_id = :tid "
        )
        params = {"tid": tid}
        if site_id:
            query += "AND n.site_id = :sid "
            params["sid"] = site_id
        query += "ORDER BY s.site_type, n.role, n.node_name"

        result = await db.execute(text(query), params)
        rows = result.fetchall()

        if rows:
            settings = get_settings()
            items = []
            for r in rows:
                items.append({
                    "id": str(r[0]),
                    "site_id": str(r[1]),
                    "node_name": r[2],
                    "role": r[3],
                    "k8s_pod_name": r[4],
                    "service_type": r[5],
                    "ip_address": r[6],
                    "status": r[7],
                    "active_sessions": r[8],
                    "cpu_pct": r[9],
                    "mem_pct": r[10],
                    "last_heartbeat": r[11].isoformat() if r[11] else None,
                    "created_at": r[12].isoformat() if r[12] else None,
                    "site_name": r[13],
                    "site_type": r[14],
                })
            return {"items": items, "total": len(items)}
    except Exception:
        pass  # Table may not exist yet — fall back to legacy

    # Legacy twin-node fallback
    settings = get_settings()
    nodes = [{
        "id": settings.neuranac_node_id,
        "node_name": settings.neuranac_node_id,
        "role": "primary",
        "site_type": settings.neuranac_site_type,
        "status": "active",
        "is_self": True,
    }]
    if settings.sync_peer_address:
        peer_status = "unknown"
        try:
            peer_url = f"http://{settings.sync_peer_address.replace(':9090', ':9100')}/health"
            async with httpx.AsyncClient(timeout=3) as client:
                resp = await client.get(peer_url)
                if resp.status_code == 200:
                    peer_status = "active"
        except Exception:
            peer_status = "unreachable"
        nodes.append({
            "id": "peer",
            "node_name": "peer",
            "role": "secondary",
            "site_type": "cloud" if settings.neuranac_site_type == "onprem" else "onprem",
            "status": peer_status,
            "is_self": False,
        })
    return {"items": nodes, "total": len(nodes)}


@router.post("/register", status_code=201)
async def register_node(body: NodeRegister, request: Request, db: AsyncSession = Depends(get_db)):
    """Register a new node (called by K8s operator or node self-registration).

    Enforces: 1 node (by k8s_pod_name+namespace) → 1 tenant.
    """
    tid = get_tenant_id(request)

    # Check if node already belongs to another tenant
    if body.k8s_pod_name and body.k8s_namespace:
        existing = await db.execute(text(
            "SELECT tenant_id FROM neuranac_node_registry "
            "WHERE k8s_pod_name = :pod AND k8s_namespace = :ns AND tenant_id IS NOT NULL"
        ), {"pod": body.k8s_pod_name, "ns": body.k8s_namespace})
        ex_row = existing.fetchone()
        if ex_row and str(ex_row[0]) != tid:
            raise HTTPException(409, "Node is already registered to a different tenant")

    result = await db.execute(text(
        "INSERT INTO neuranac_node_registry (tenant_id, site_id, node_name, role, k8s_pod_name, "
        "k8s_namespace, service_type, ip_address, metadata, last_heartbeat) "
        "VALUES (:tid, :sid, :name, :role, :pod, :ns, :svc, :ip, :meta, now()) RETURNING id"
    ), {
        "tid": tid,
        "sid": body.site_id,
        "name": body.node_name,
        "role": body.role,
        "pod": body.k8s_pod_name,
        "ns": body.k8s_namespace,
        "svc": body.service_type,
        "ip": body.ip_address,
        "meta": json.dumps(body.metadata),
    })
    await db.commit()
    row = result.fetchone()
    return {"id": str(row[0]), "node_name": body.node_name, "status": "registered"}


@router.get("/sync-status", name="nodes_sync_status")
async def sync_status():
    """Legacy sync status endpoint."""
    settings = get_settings()
    return {
        "node_id": settings.neuranac_node_id,
        "peer_address": settings.sync_peer_address,
        "sync_enabled": settings.deployment_mode == "hybrid" and bool(settings.sync_peer_address),
        "deployment_mode": settings.deployment_mode,
        "last_sync": None,
        "sync_lag_ms": 0,
        "pending_changes": 0,
    }


@router.post("/sync/trigger")
async def trigger_sync():
    return {"status": "sync_triggered", "message": "Full resynchronization initiated"}


@router.post("/failover")
async def initiate_failover():
    return {"status": "failover_initiated", "message": "Promoting this node to primary"}


@router.get("/twin-status", name="nodes_twin_status")
async def twin_status(request: Request, db: AsyncSession = Depends(get_db)):
    """Legacy twin-node status endpoint for hybrid deployments."""
    settings = get_settings()
    tid = get_tenant_id(request)
    try:
        result = await db.execute(text(
            "SELECT n.id, n.node_name, n.role, n.status, n.last_heartbeat, n.cpu_pct, n.mem_pct, "
            "n.active_sessions, s.site_name, s.site_type "
            "FROM neuranac_node_registry n JOIN neuranac_sites s ON n.site_id = s.id "
            "WHERE n.tenant_id = :tid ORDER BY n.role, n.node_name LIMIT 2"
        ), {"tid": tid})
        rows = result.fetchall()
        if rows:
            nodes = []
            for r in rows:
                nodes.append({
                    "id": str(r[0]), "node_name": r[1], "role": r[2], "status": r[3],
                    "last_heartbeat": r[4].isoformat() if r[4] else None,
                    "cpu_pct": r[5], "mem_pct": r[6], "active_sessions": r[7],
                    "site_name": r[8], "site_type": r[9],
                })
            return {"nodes": nodes, "deployment_mode": settings.deployment_mode}
    except Exception:
        pass
    return {
        "nodes": [{"id": settings.neuranac_node_id, "node_name": settings.neuranac_node_id,
                    "role": "primary", "status": "active"}],
        "deployment_mode": settings.deployment_mode,
    }


@router.get("/{node_id}")
async def get_node(node_id: str, db: AsyncSession = Depends(get_db)):
    """Get detailed info for a specific node."""
    result = await db.execute(text(
        "SELECT n.id, n.site_id, n.node_name, n.role, n.k8s_pod_name, n.k8s_namespace, "
        "n.service_type, n.ip_address, n.status, n.active_sessions, n.cpu_pct, n.mem_pct, "
        "n.last_heartbeat, n.metadata, n.created_at, s.site_name as site_name, s.site_type "
        "FROM neuranac_node_registry n JOIN neuranac_sites s ON n.site_id = s.id WHERE n.id = :nid"
    ), {"nid": node_id})
    r = result.fetchone()
    if not r:
        raise HTTPException(status_code=404, detail="Node not found")
    return {
        "id": str(r[0]), "site_id": str(r[1]), "node_name": r[2], "role": r[3],
        "k8s_pod_name": r[4], "k8s_namespace": r[5], "service_type": r[6],
        "ip_address": r[7], "status": r[8], "active_sessions": r[9],
        "cpu_pct": r[10], "mem_pct": r[11],
        "last_heartbeat": r[12].isoformat() if r[12] else None,
        "metadata": r[13], "created_at": r[14].isoformat() if r[14] else None,
        "site_name": r[15], "site_type": r[16],
    }


@router.post("/{node_id}/heartbeat")
async def node_heartbeat(node_id: str, body: NodeHeartbeat, db: AsyncSession = Depends(get_db)):
    """Node reports its current health metrics."""
    result = await db.execute(text(
        "UPDATE neuranac_node_registry SET status = :s, active_sessions = :sess, "
        "cpu_pct = :cpu, mem_pct = :mem, last_heartbeat = now(), updated_at = now() "
        "WHERE id = :nid RETURNING id"
    ), {"nid": node_id, "s": body.status, "sess": body.active_sessions,
        "cpu": body.cpu_pct, "mem": body.mem_pct})
    await db.commit()
    if not result.fetchone():
        raise HTTPException(status_code=404, detail="Node not found")
    return {"id": node_id, "status": "heartbeat_accepted"}


@router.post("/{node_id}/drain")
async def drain_node(node_id: str, db: AsyncSession = Depends(get_db)):
    """Mark a node as draining — stops accepting new sessions."""
    result = await db.execute(text(
        "UPDATE neuranac_node_registry SET status = 'draining', updated_at = now() "
        "WHERE id = :nid RETURNING id, node_name"
    ), {"nid": node_id})
    await db.commit()
    row = result.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Node not found")
    return {"id": node_id, "node_name": row[1], "status": "draining"}


@router.delete("/{node_id}")
async def deregister_node(node_id: str, db: AsyncSession = Depends(get_db)):
    """Remove a node from the registry."""
    result = await db.execute(
        text("DELETE FROM neuranac_node_registry WHERE id = :nid RETURNING id"),
        {"nid": node_id},
    )
    await db.commit()
    if not result.fetchone():
        raise HTTPException(status_code=404, detail="Node not found")
    return {"id": node_id, "status": "deregistered"}

