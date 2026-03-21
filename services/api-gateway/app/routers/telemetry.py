"""Telemetry router - query ingested network telemetry data (SNMP, Syslog, NetFlow, DHCP, Neighbors)"""
from uuid import UUID
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, func

from app.database.session import get_db

router = APIRouter()


# ─── Telemetry Events (SNMP traps, syslog) ──────────────────────────────────

@router.get("/events")
async def list_telemetry_events(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    event_type: Optional[str] = Query(None, description="Filter: snmp, syslog, dhcp, neighbor"),
    source_ip: Optional[str] = Query(None),
    severity: Optional[str] = Query(None),
    since_hours: Optional[int] = Query(None, description="Events from last N hours"),
    db: AsyncSession = Depends(get_db),
):
    """List telemetry events with filtering and pagination."""
    where_clauses = []
    params = {"skip": skip, "limit": limit}

    if event_type:
        where_clauses.append("event_type = :event_type")
        params["event_type"] = event_type
    if source_ip:
        where_clauses.append("source_ip = CAST(:source_ip AS inet)")
        params["source_ip"] = source_ip
    if severity:
        where_clauses.append("severity = :severity")
        params["severity"] = severity
    if since_hours:
        where_clauses.append("created_at >= :since")
        params["since"] = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=since_hours)

    where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"

    count_result = await db.execute(
        text(f"SELECT COUNT(*) FROM neuranac_telemetry_events WHERE {where_sql}"), params
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        text(f"""
            SELECT id, event_type, source_ip::text, site_id, node_id, severity,
                   facility, trap_oid, message, raw_data, created_at
            FROM neuranac_telemetry_events
            WHERE {where_sql}
            ORDER BY created_at DESC
            OFFSET :skip LIMIT :limit
        """), params
    )
    rows = result.mappings().all()

    return {
        "items": [dict(r) for r in rows],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get("/events/summary")
async def telemetry_events_summary(
    since_hours: int = Query(24, description="Summary for last N hours"),
    db: AsyncSession = Depends(get_db),
):
    """Aggregate telemetry event counts by type and severity."""
    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=since_hours)
    result = await db.execute(
        text("""
            SELECT event_type, severity, COUNT(*) as count
            FROM neuranac_telemetry_events
            WHERE created_at >= :since
            GROUP BY event_type, severity
            ORDER BY count DESC
        """),
        {"since": since},
    )
    rows = result.mappings().all()
    return {"since_hours": since_hours, "summary": [dict(r) for r in rows]}


# ─── NetFlow / IPFIX Flows ──────────────────────────────────────────────────

@router.get("/flows")
async def list_flows(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    exporter_ip: Optional[str] = Query(None),
    src_ip: Optional[str] = Query(None),
    dst_ip: Optional[str] = Query(None),
    protocol: Optional[int] = Query(None),
    dst_port: Optional[int] = Query(None),
    since_hours: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List NetFlow/IPFIX flow records with filtering."""
    where_clauses = []
    params = {"skip": skip, "limit": limit}

    if exporter_ip:
        where_clauses.append("exporter_ip = CAST(:exporter_ip AS inet)")
        params["exporter_ip"] = exporter_ip
    if src_ip:
        where_clauses.append("src_ip = CAST(:src_ip AS inet)")
        params["src_ip"] = src_ip
    if dst_ip:
        where_clauses.append("dst_ip = CAST(:dst_ip AS inet)")
        params["dst_ip"] = dst_ip
    if protocol is not None:
        where_clauses.append("protocol = :protocol")
        params["protocol"] = protocol
    if dst_port is not None:
        where_clauses.append("dst_port = :dst_port")
        params["dst_port"] = dst_port
    if since_hours:
        where_clauses.append("created_at >= :since")
        params["since"] = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=since_hours)

    where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"

    count_result = await db.execute(
        text(f"SELECT COUNT(*) FROM neuranac_telemetry_flows WHERE {where_sql}"), params
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        text(f"""
            SELECT id, exporter_ip::text, site_id, version,
                   src_ip::text, dst_ip::text, src_port, dst_port, protocol,
                   packets, bytes, tos, next_hop::text, created_at
            FROM neuranac_telemetry_flows
            WHERE {where_sql}
            ORDER BY created_at DESC
            OFFSET :skip LIMIT :limit
        """), params
    )
    rows = result.mappings().all()
    return {"items": [dict(r) for r in rows], "total": total, "skip": skip, "limit": limit}


@router.get("/flows/top-talkers")
async def top_talkers(
    since_hours: int = Query(1),
    limit: int = Query(10, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Top N source IPs by bytes transferred."""
    since = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=since_hours)
    result = await db.execute(
        text("""
            SELECT src_ip::text, SUM(bytes) as total_bytes, SUM(packets) as total_packets,
                   COUNT(*) as flow_count
            FROM neuranac_telemetry_flows
            WHERE created_at >= :since AND src_ip IS NOT NULL
            GROUP BY src_ip
            ORDER BY total_bytes DESC
            LIMIT :limit
        """),
        {"since": since, "limit": limit},
    )
    rows = result.mappings().all()
    return {"since_hours": since_hours, "top_talkers": [dict(r) for r in rows]}


# ─── DHCP Fingerprints ──────────────────────────────────────────────────────

@router.get("/dhcp")
async def list_dhcp_fingerprints(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    mac: Optional[str] = Query(None),
    hostname: Optional[str] = Query(None),
    os_guess: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List DHCP fingerprint records."""
    where_clauses = []
    params = {"skip": skip, "limit": limit}

    if mac:
        where_clauses.append("mac_address = CAST(:mac AS macaddr)")
        params["mac"] = mac
    if hostname:
        where_clauses.append("hostname ILIKE :hostname")
        params["hostname"] = f"%{hostname}%"
    if os_guess:
        where_clauses.append("os_guess ILIKE :os_guess")
        params["os_guess"] = f"%{os_guess}%"

    where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"

    count_result = await db.execute(
        text(f"SELECT COUNT(*) FROM neuranac_dhcp_fingerprints WHERE {where_sql}"), params
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        text(f"""
            SELECT id, mac_address::text, client_ip::text, hostname, vendor_class,
                   fingerprint, os_guess, msg_type, source_ip::text, site_id, created_at
            FROM neuranac_dhcp_fingerprints
            WHERE {where_sql}
            ORDER BY created_at DESC
            OFFSET :skip LIMIT :limit
        """), params
    )
    rows = result.mappings().all()
    return {"items": [dict(r) for r in rows], "total": total, "skip": skip, "limit": limit}


@router.get("/dhcp/os-distribution")
async def dhcp_os_distribution(db: AsyncSession = Depends(get_db)):
    """Get distribution of OS types from DHCP fingerprinting."""
    result = await db.execute(
        text("""
            SELECT os_guess, COUNT(DISTINCT mac_address) as device_count
            FROM neuranac_dhcp_fingerprints
            WHERE os_guess IS NOT NULL AND os_guess != 'Unknown'
            GROUP BY os_guess
            ORDER BY device_count DESC
        """)
    )
    rows = result.mappings().all()
    return {"os_distribution": [dict(r) for r in rows]}


# ─── Neighbor Topology (CDP/LLDP) ───────────────────────────────────────────

@router.get("/neighbors")
async def list_neighbors(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    local_device_ip: Optional[str] = Query(None),
    protocol: Optional[str] = Query(None, description="cdp or lldp"),
    db: AsyncSession = Depends(get_db),
):
    """List CDP/LLDP neighbor topology entries."""
    where_clauses = []
    params = {"skip": skip, "limit": limit}

    if local_device_ip:
        where_clauses.append("local_device_ip = CAST(:local_device_ip AS inet)")
        params["local_device_ip"] = local_device_ip
    if protocol:
        where_clauses.append("protocol = :protocol")
        params["protocol"] = protocol

    where_sql = " AND ".join(where_clauses) if where_clauses else "TRUE"

    count_result = await db.execute(
        text(f"SELECT COUNT(*) FROM neuranac_neighbor_topology WHERE {where_sql}"), params
    )
    total = count_result.scalar() or 0

    result = await db.execute(
        text(f"""
            SELECT id, local_device_ip::text, local_port, remote_device, remote_port,
                   remote_ip::text, platform, protocol, site_id, last_seen, created_at
            FROM neuranac_neighbor_topology
            WHERE {where_sql}
            ORDER BY last_seen DESC
            OFFSET :skip LIMIT :limit
        """), params
    )
    rows = result.mappings().all()
    return {"items": [dict(r) for r in rows], "total": total, "skip": skip, "limit": limit}


@router.get("/neighbors/topology-map")
async def topology_map(db: AsyncSession = Depends(get_db)):
    """Build a simplified topology graph from neighbor data."""
    result = await db.execute(
        text("""
            SELECT local_device_ip::text, local_port, remote_device, remote_port,
                   remote_ip::text, platform, protocol
            FROM neuranac_neighbor_topology
            ORDER BY local_device_ip, local_port
        """)
    )
    rows = result.mappings().all()

    nodes = set()
    edges = []
    for r in rows:
        local = r["local_device_ip"]
        remote = r["remote_device"]
        nodes.add(local)
        nodes.add(remote)
        edges.append({
            "from": local,
            "from_port": r["local_port"],
            "to": remote,
            "to_port": r["remote_port"],
            "protocol": r["protocol"],
            "platform": r["platform"],
        })

    return {
        "nodes": list(nodes),
        "edges": edges,
        "node_count": len(nodes),
        "edge_count": len(edges),
    }


# ─── Collector Status ────────────────────────────────────────────────────────

@router.get("/collectors")
async def list_collectors(db: AsyncSession = Depends(get_db)):
    """List active ingestion collector instances and their stats."""
    result = await db.execute(
        text("""
            SELECT id, node_id, site_id, status, channels, stats, last_heartbeat, created_at
            FROM neuranac_ingestion_collectors
            ORDER BY last_heartbeat DESC
        """)
    )
    rows = result.mappings().all()
    return {"collectors": [dict(r) for r in rows]}


@router.get("/health")
async def telemetry_health(db: AsyncSession = Depends(get_db)):
    """Telemetry subsystem health check — verifies tables exist and recent data."""
    tables = [
        "neuranac_telemetry_events",
        "neuranac_telemetry_flows",
        "neuranac_dhcp_fingerprints",
        "neuranac_neighbor_topology",
        "neuranac_ingestion_collectors",
    ]
    checks = {}
    for table in tables:
        try:
            result = await db.execute(text(f"SELECT COUNT(*) FROM {table}"))
            count = result.scalar()
            checks[table] = {"exists": True, "row_count": count}
        except Exception as e:
            checks[table] = {"exists": False, "error": str(e)}

    all_ok = all(c.get("exists", False) for c in checks.values())
    return {
        "status": "healthy" if all_ok else "degraded",
        "tables": checks,
    }
