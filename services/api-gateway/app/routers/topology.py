"""Topology router — aggregated view of all NeuraNAC components, services, devices, and data flows."""
import time
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, Query
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.database.session import get_db
from app.middleware.auth import require_permission
from app.models.network import NetworkDevice, Session, Endpoint

router = APIRouter()


# ─── Service health probes ────────────────────────────────────────────────────

async def _probe_service(name: str, url: str, timeout: float = 3.0) -> dict:
    """Probe a service health endpoint and return status + latency."""
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            t0 = time.monotonic()
            resp = await client.get(url)
            latency_ms = round((time.monotonic() - t0) * 1000, 1)
            status = "healthy" if resp.status_code == 200 else "degraded"
            return {"name": name, "url": url, "status": status, "latency_ms": latency_ms}
    except Exception as e:
        return {"name": name, "url": url, "status": "unreachable", "latency_ms": None, "error": str(e)}


# ─── Full topology endpoint ──────────────────────────────────────────────────

@router.get("/", dependencies=[Depends(require_permission("network:read"))])
async def get_topology(
    view: Optional[str] = Query("physical", description="View type: physical, logical, dataflow, legacy_nac"),
    db: AsyncSession = Depends(get_db),
):
    """
    Return aggregated topology data for visualization.

    Views:
    - **physical**: Endpoints → NADs → NeuraNAC services → Identity Sources
    - **logical**: Internal service mesh (API GW, RADIUS, Policy, AI, DB, Redis, NATS)
    - **dataflow**: End-to-end RADIUS auth request trace
    - **legacy_nac**: Legacy NAC ↔ NeuraNAC integration topology
    """
    settings = get_settings()

    # ── Probe all services ───────────────────────────────────────────────
    service_urls = [
        ("api-gateway", f"http://localhost:{settings.api_port}/health"),
        ("radius-server", "http://radius-server:9100/health"),
        ("policy-engine", "http://policy-engine:8082/health"),
        ("ai-engine", f"http://{settings.ai_engine_host}:{settings.ai_engine_port}/health"),
        ("sync-engine", "http://sync-engine:9100/health"),
    ]
    services = []
    for name, url in service_urls:
        services.append(await _probe_service(name, url))

    # ── Infrastructure probes ────────────────────────────────────────────
    infra = []
    # PostgreSQL
    try:
        t0 = time.monotonic()
        await db.execute(text("SELECT 1"))
        latency = round((time.monotonic() - t0) * 1000, 1)
        infra.append({"name": "postgres", "type": "database", "port": settings.postgres_port,
                       "status": "healthy", "latency_ms": latency})
    except Exception:
        infra.append({"name": "postgres", "type": "database", "port": settings.postgres_port,
                       "status": "unreachable"})

    # Redis
    try:
        from app.database.redis import get_redis
        rdb = get_redis()
        if rdb:
            t0 = time.monotonic()
            await rdb.ping()
            latency = round((time.monotonic() - t0) * 1000, 1)
            infra.append({"name": "redis", "type": "cache", "port": settings.redis_port,
                           "status": "healthy", "latency_ms": latency})
        else:
            infra.append({"name": "redis", "type": "cache", "port": settings.redis_port,
                           "status": "unavailable"})
    except Exception:
        infra.append({"name": "redis", "type": "cache", "port": settings.redis_port,
                       "status": "unreachable"})

    # NATS
    try:
        nats_host = settings.nats_url.replace("nats://", "").split(",")[0].split(":")[0]
        async with httpx.AsyncClient(timeout=2) as client:
            resp = await client.get(f"http://{nats_host}:8222/varz")
            nats_status = "healthy" if resp.status_code == 200 else "degraded"
    except Exception:
        nats_status = "unreachable"
    infra.append({"name": "nats", "type": "messaging", "port": 4222, "status": nats_status})

    # ── Network devices (NADs) ───────────────────────────────────────────
    nad_count = await db.scalar(select(func.count()).select_from(NetworkDevice)) or 0
    nad_result = await db.execute(
        select(NetworkDevice).order_by(NetworkDevice.created_at.desc()).limit(100)
    )
    nads = [
        {
            "id": str(d.id), "name": d.name, "ip_address": d.ip_address,
            "device_type": d.device_type, "vendor": d.vendor, "model": d.model,
            "status": d.status, "location": d.location,
        }
        for d in nad_result.scalars().all()
    ]

    # ── Active sessions ──────────────────────────────────────────────────
    active_sessions = await db.scalar(
        select(func.count()).select_from(Session).where(Session.is_active == True)
    ) or 0
    total_sessions = await db.scalar(select(func.count()).select_from(Session)) or 0

    # ── Endpoints ────────────────────────────────────────────────────────
    endpoint_count = await db.scalar(select(func.count()).select_from(Endpoint)) or 0

    # ── legacy connections ──────────────────────────────────────────────────
    legacy_nac_connections = []
    try:
        lnac_result = await db.execute(text(
            "SELECT id, name, hostname, port, detected_version, connection_status, "
            "deployment_mode, event_stream_status, is_active "
            "FROM legacy_nac_connections ORDER BY created_at DESC LIMIT 20"
        ))
        legacy_nac_connections = [
            {"id": str(r[0]), "name": r[1], "hostname": r[2], "port": r[3],
             "legacy_nac_version": r[4], "status": r[5], "deployment_mode": r[6],
             "event_stream_status": r[7], "is_active": r[8]}
            for r in lnac_result.fetchall()
        ]
    except Exception:
        pass  # NeuraNAC tables may not exist in minimal deployments

    # ── Twin nodes ───────────────────────────────────────────────────────
    nodes = [{"id": settings.neuranac_node_id, "role": "primary",
              "site_type": settings.neuranac_site_type, "status": "healthy"}]
    if settings.sync_peer_address:
        peer_status = "unknown"
        try:
            peer_url = f"http://{settings.sync_peer_address.replace(':9090', ':9100')}/health"
            async with httpx.AsyncClient(timeout=2) as client:
                resp = await client.get(peer_url)
                peer_status = "healthy" if resp.status_code == 200 else "degraded"
        except Exception:
            peer_status = "unreachable"
        nodes.append({"id": "peer", "role": "secondary",
                       "site_type": "cloud" if settings.neuranac_site_type == "onprem" else "onprem",
                       "status": peer_status})

    # ── Edges (connections between components) ───────────────────────────
    edges = [
        {"from": "endpoints", "to": "network_devices", "protocol": "802.1X / MAB",
         "label": f"{active_sessions} active", "active_count": active_sessions},
        {"from": "network_devices", "to": "radius-server", "protocol": "RADIUS UDP 1812/1813",
         "label": "Auth + Acct", "active_count": nad_count},
        {"from": "radius-server", "to": "policy-engine", "protocol": "gRPC / mTLS",
         "label": "Policy Eval"},
        {"from": "radius-server", "to": "ai-engine", "protocol": "HTTP",
         "label": "Profile + Risk + Anomaly"},
        {"from": "api-gateway", "to": "postgres", "protocol": "SQL (asyncpg)",
         "label": "CRUD + Sessions"},
        {"from": "api-gateway", "to": "redis", "protocol": "Redis Protocol",
         "label": "Cache + Rate Limit"},
        {"from": "radius-server", "to": "nats", "protocol": "NATS JetStream",
         "label": "Session Events"},
        {"from": "sync-engine", "to": "nats", "protocol": "NATS JetStream",
         "label": "Replication"},
        {"from": "sync-engine", "to": "postgres", "protocol": "SQL",
         "label": "Data Sync"},
        {"from": "web-ui", "to": "api-gateway", "protocol": "REST / WebSocket",
         "label": "UI Requests"},
    ]

    # NeuraNAC-specific edges (only when NeuraNAC is enabled)
    settings = get_settings()
    if settings.legacy_nac_enabled and legacy_nac_connections:
        edges.append({"from": "api-gateway", "to": "legacy_nac", "protocol": "ERS API / HTTPS",
                       "label": f"{len(legacy_nac_connections)} connection(s)"})
        for lnac_conn in legacy_nac_connections:
            if lnac_conn.get("event_stream_status") in ("connected", "simulated"):
                edges.append({"from": "legacy_nac", "to": "api-gateway", "protocol": "Event Stream / WebSocket",
                               "label": "Real-time Events"})
                break

    # ── Layer definitions for UI rendering ───────────────────────────────
    layers = {
        "physical": {
            "description": "Physical topology: Endpoints → NADs → NeuraNAC Services → Identity Sources",
            "layers": [
                {"name": "Endpoints", "icon": "monitor", "count": endpoint_count,
                 "items": [{"type": "endpoint_group", "count": endpoint_count, "label": f"{endpoint_count} endpoints"}]},
                {"name": "Network Access Devices", "icon": "router", "count": nad_count, "items": nads},
                {"name": "NeuraNAC Services", "icon": "server", "items": services},
                {"name": "Infrastructure", "icon": "database", "items": infra},
            ],
        },
        "logical": {
            "description": "Logical service mesh: internal component connections and protocols",
            "components": [
                {"name": "Web UI", "type": "frontend", "port": 3001, "status": "healthy", "tech": "React + Vite"},
                *[{"name": s["name"], "type": "service", "status": s["status"],
                   "latency_ms": s.get("latency_ms")} for s in services],
                *[{"name": i["name"], "type": i["type"], "port": i["port"],
                   "status": i["status"]} for i in infra],
            ],
            "connections": edges,
        },
        "dataflow": {
            "description": "RADIUS authentication request trace — end-to-end data flow",
            "steps": [
                {"step": 1, "component": "Endpoint", "action": "Sends 802.1X EAPOL-Start or connects to port",
                 "protocol": "802.1X / MAB", "icon": "monitor"},
                {"step": 2, "component": "NAD (Switch/AP)", "action": "Converts to RADIUS Access-Request, sends to NeuraNAC",
                 "protocol": "RADIUS UDP 1812", "icon": "router"},
                {"step": 3, "component": "RADIUS Server", "action": "Parses packet, validates NAD, determines auth type",
                 "protocol": "Internal", "icon": "shield"},
                {"step": 4, "component": "AI Engine", "action": "Endpoint profiling, risk scoring, anomaly detection",
                 "protocol": "HTTP :8081", "icon": "brain"},
                {"step": 5, "component": "Policy Engine", "action": "Evaluates policy conditions, determines VLAN/SGT/action",
                 "protocol": "gRPC :9091", "icon": "shield-check"},
                {"step": 6, "component": "RADIUS Server", "action": "Builds Access-Accept/Reject with attributes",
                 "protocol": "RADIUS UDP", "icon": "shield"},
                {"step": 7, "component": "NAD (Switch/AP)", "action": "Applies VLAN, SGT, ACL to port",
                 "protocol": "802.1X", "icon": "router"},
                {"step": 8, "component": "NATS / Database", "action": "Session created, audit logged, metrics emitted",
                 "protocol": "NATS + SQL", "icon": "database"},
                {"step": 9, "component": "CoA (if risk critical)", "action": "RADIUS CoA Disconnect/Reauth sent to NAD",
                 "protocol": "RADIUS UDP 3799", "icon": "alert-triangle", "conditional": True},
            ],
        },
        "legacy_nac": {
            "description": "Legacy NAC ↔ NeuraNAC integration topology",
            "legacy_nac_connections": legacy_nac_connections,
            "integration_points": [
                {"name": "ERS API Sync", "direction": "Legacy NAC → NeuraNAC", "protocol": "HTTPS :9060",
                 "entities": ["network_device", "internal_user", "endpoint", "sgt"]},
                {"name": "Bidirectional Sync", "direction": "Legacy NAC ↔ NeuraNAC", "protocol": "HTTPS :9060",
                 "entities": ["network_device", "internal_user", "endpoint", "sgt"]},
                {"name": "Event Stream", "direction": "Legacy NAC → NeuraNAC", "protocol": "WebSocket / STOMP :8910",
                 "entities": ["session", "profiler", "trustsec"]},
                {"name": "Policy Translation", "direction": "Legacy NAC → NeuraNAC", "protocol": "AI-assisted",
                 "entities": ["authorization_policy"]},
                {"name": "RADIUS Traffic Analysis", "direction": "Both", "protocol": "Snapshot + Compare",
                 "entities": ["radius_snapshot"]},
                {"name": "Zero-Touch Migration", "direction": "Legacy NAC → NeuraNAC", "protocol": "8-step wizard",
                 "entities": ["all"]},
            ],
        },
    }

    # Return requested view or all
    selected_view = layers.get(view, layers)
    if view and view in layers:
        selected_view = layers[view]

    return {
        "view": view,
        "summary": {
            "services_total": len(services),
            "services_healthy": sum(1 for s in services if s["status"] == "healthy"),
            "infra_total": len(infra),
            "infra_healthy": sum(1 for i in infra if i["status"] == "healthy"),
            "network_devices": nad_count,
            "endpoints": endpoint_count,
            "active_sessions": active_sessions,
            "total_sessions": total_sessions,
            "legacy_nac_connections": len(legacy_nac_connections),
            "twin_nodes": len(nodes),
        },
        "services": services,
        "infrastructure": infra,
        "network_devices": {"items": nads, "total": nad_count},
        "endpoints_total": endpoint_count,
        "sessions": {"active": active_sessions, "total": total_sessions},
        "legacy_nac_connections": legacy_nac_connections,
        "nodes": nodes,
        "edges": edges,
        "layers": selected_view,
    }


@router.get("/health-matrix", dependencies=[Depends(require_permission("network:read"))])
async def topology_health_matrix():
    """Quick health matrix of all services for topology status indicators."""
    settings = get_settings()
    probes = [
        ("api-gateway", f"http://localhost:{settings.api_port}/health"),
        ("radius-server", "http://radius-server:9100/health"),
        ("policy-engine", "http://policy-engine:8082/health"),
        ("ai-engine", f"http://{settings.ai_engine_host}:{settings.ai_engine_port}/health"),
        ("sync-engine", "http://sync-engine:9100/health"),
    ]
    results = {}
    for name, url in probes:
        probe = await _probe_service(name, url, timeout=2.0)
        results[name] = {"status": probe["status"], "latency_ms": probe.get("latency_ms")}

    healthy_count = sum(1 for v in results.values() if v["status"] == "healthy")
    overall = "healthy" if healthy_count == len(results) else (
        "degraded" if healthy_count > 0 else "critical"
    )
    return {"overall": overall, "services": results, "healthy": healthy_count, "total": len(results)}
