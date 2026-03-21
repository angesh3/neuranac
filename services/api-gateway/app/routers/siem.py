"""SIEM Integration router - Syslog, CEF, webhook forwarding to SIEM/SOAR platforms.

All SIEM destinations and SOAR playbooks are persisted in PostgreSQL
(neuranac_siem_destinations / neuranac_soar_playbooks tables) so they survive restarts.
"""
import json
import socket
import time
from datetime import datetime, timezone
from typing import Optional, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.database.session import get_db
from app.middleware.auth import require_permission

router = APIRouter()


# ─── Syslog / CEF Forwarder ─────────────────────────────────────────────────

class SIEMDestination(BaseModel):
    name: str
    dest_type: str  # "syslog_udp", "syslog_tcp", "syslog_tls", "cef", "webhook"
    host: str
    port: int = 514
    protocol: str = "udp"  # udp, tcp, tls
    format: str = "cef"  # cef, leef, json, syslog_rfc5424
    webhook_url: Optional[str] = None
    webhook_headers: Optional[dict] = None
    filters: Optional[dict] = None  # e.g. {"severity": "high", "event_types": ["auth_failure"]}
    enabled: bool = True


async def _ensure_siem_tables(db: AsyncSession):
    """Create SIEM tables if they don't exist (idempotent)."""
    await db.execute(text("""
        CREATE TABLE IF NOT EXISTS neuranac_siem_destinations (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            name VARCHAR(255) NOT NULL,
            dest_type VARCHAR(50) NOT NULL,
            host VARCHAR(255) NOT NULL,
            port INT DEFAULT 514,
            protocol VARCHAR(10) DEFAULT 'udp',
            format VARCHAR(20) DEFAULT 'cef',
            webhook_url TEXT,
            webhook_headers JSONB DEFAULT '{}',
            filters JSONB DEFAULT '{}',
            enabled BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
    """))
    await db.execute(text("""
        CREATE TABLE IF NOT EXISTS neuranac_soar_playbooks (
            id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
            name VARCHAR(255) NOT NULL,
            trigger_event VARCHAR(100) NOT NULL,
            webhook_url TEXT NOT NULL,
            webhook_headers JSONB DEFAULT '{}',
            enabled BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """))
    await db.commit()


def _row_to_dest(row) -> dict:
    """Convert a DB row mapping to a SIEM destination dict."""
    return {
        "id": str(row["id"]),
        "name": row["name"],
        "dest_type": row["dest_type"],
        "host": row["host"],
        "port": row["port"],
        "protocol": row["protocol"],
        "format": row["format"],
        "webhook_url": row["webhook_url"],
        "webhook_headers": row["webhook_headers"] or {},
        "filters": row["filters"] or {},
        "enabled": row["enabled"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }


@router.get("/destinations", dependencies=[Depends(require_permission("siem:read"))])
async def list_siem_destinations(db: AsyncSession = Depends(get_db)):
    await _ensure_siem_tables(db)
    result = await db.execute(text(
        "SELECT * FROM neuranac_siem_destinations ORDER BY created_at DESC"
    ))
    rows = result.mappings().all()
    items = [_row_to_dest(r) for r in rows]
    return {"items": items, "total": len(items)}


@router.post("/destinations", status_code=201, dependencies=[Depends(require_permission("siem:manage"))])
async def add_siem_destination(req: SIEMDestination, db: AsyncSession = Depends(get_db)):
    await _ensure_siem_tables(db)
    result = await db.execute(text("""
        INSERT INTO neuranac_siem_destinations
            (name, dest_type, host, port, protocol, format, webhook_url, webhook_headers, filters, enabled)
        VALUES
            (:name, :dest_type, :host, :port, :protocol, :format, :webhook_url,
             CAST(:webhook_headers AS jsonb), CAST(:filters AS jsonb), :enabled)
        RETURNING *
    """), {
        "name": req.name, "dest_type": req.dest_type, "host": req.host,
        "port": req.port, "protocol": req.protocol, "format": req.format,
        "webhook_url": req.webhook_url,
        "webhook_headers": json.dumps(req.webhook_headers or {}),
        "filters": json.dumps(req.filters or {}),
        "enabled": req.enabled,
    })
    await db.commit()
    row = result.mappings().first()
    return _row_to_dest(row)


@router.delete("/destinations/{dest_id}", status_code=204, dependencies=[Depends(require_permission("siem:manage"))])
async def remove_siem_destination(dest_id: str, db: AsyncSession = Depends(get_db)):
    await db.execute(text("DELETE FROM neuranac_siem_destinations WHERE id = :id"), {"id": dest_id})
    await db.commit()


async def _get_dest_by_id(dest_id: str, db: AsyncSession) -> dict:
    """Fetch a single SIEM destination by ID or raise 404."""
    result = await db.execute(
        text("SELECT * FROM neuranac_siem_destinations WHERE id = :id"), {"id": dest_id}
    )
    row = result.mappings().first()
    if not row:
        raise HTTPException(404, "Destination not found")
    return _row_to_dest(row)


@router.post("/destinations/{dest_id}/test", dependencies=[Depends(require_permission("siem:manage"))])
async def test_siem_destination(dest_id: str, db: AsyncSession = Depends(get_db)):
    dest = await _get_dest_by_id(dest_id, db)
    try:
        if dest["dest_type"] in ("syslog_udp", "syslog_tcp", "cef"):
            test_msg = _format_cef("NeuraNAC", "Test", "1", "SIEM connectivity test", 1)
            _send_syslog(dest["host"], dest["port"], dest.get("protocol", "udp"), test_msg)
            return {"status": "success", "message": f"Test event sent to {dest['host']}:{dest['port']}"}
        elif dest["dest_type"] == "webhook":
            import httpx
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.post(
                    dest.get("webhook_url", ""),
                    json={"test": True, "source": "neuranac", "timestamp": datetime.now(timezone.utc).replace(tzinfo=None).isoformat()},
                    headers=dest.get("webhook_headers") or {},
                )
                return {"status": "success", "http_status": resp.status_code}
        return {"status": "unsupported_type"}
    except Exception as e:
        return {"status": "failed", "error": str(e)}


# ─── Event Forwarding ────────────────────────────────────────────────────────

class ForwardEventRequest(BaseModel):
    event_type: str  # "auth_success", "auth_failure", "coa_sent", "posture_noncompliant", etc.
    severity: str = "medium"
    source: str = "neuranac"
    details: dict = {}


@router.post("/forward", dependencies=[Depends(require_permission("siem:manage"))])
async def forward_event(req: ForwardEventRequest, db: AsyncSession = Depends(get_db)):
    """Forward a security event to all enabled SIEM destinations"""
    result = await db.execute(text(
        "SELECT * FROM neuranac_siem_destinations WHERE enabled = TRUE"
    ))
    destinations = [_row_to_dest(r) for r in result.mappings().all()]

    results = []
    for dest in destinations:
        # Apply filters
        filters = dest.get("filters") or {}
        if filters.get("severity") and req.severity != filters["severity"]:
            continue
        if filters.get("event_types") and req.event_type not in filters["event_types"]:
            continue

        try:
            if dest["format"] == "cef":
                msg = _format_cef("NeuraNAC", req.event_type, _severity_to_cef(req.severity),
                                  json.dumps(req.details), _severity_to_int(req.severity))
                _send_syslog(dest["host"], dest["port"], dest.get("protocol", "udp"), msg)
            elif dest["format"] == "json":
                msg = json.dumps({
                    "timestamp": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
                    "event_type": req.event_type,
                    "severity": req.severity,
                    "source": req.source,
                    "details": req.details,
                })
                _send_syslog(dest["host"], dest["port"], dest.get("protocol", "udp"), msg)
            elif dest["dest_type"] == "webhook":
                import httpx
                async with httpx.AsyncClient(timeout=5) as client:
                    await client.post(
                        dest.get("webhook_url", ""),
                        json={"event_type": req.event_type, "severity": req.severity, "details": req.details},
                        headers=dest.get("webhook_headers") or {},
                    )
            results.append({"dest_id": dest["id"], "status": "sent"})
        except Exception as e:
            results.append({"dest_id": dest["id"], "status": "failed", "error": str(e)})

    return {"forwarded": len([r for r in results if r["status"] == "sent"]),
            "failed": len([r for r in results if r["status"] == "failed"]),
            "results": results}


# ─── SOAR Playbook Triggers ──────────────────────────────────────────────────

class SOARPlaybook(BaseModel):
    name: str
    trigger_event: str  # event type that triggers this playbook
    webhook_url: str
    webhook_headers: dict = {}
    enabled: bool = True


def _row_to_playbook(row) -> dict:
    return {
        "id": str(row["id"]),
        "name": row["name"],
        "trigger_event": row["trigger_event"],
        "webhook_url": row["webhook_url"],
        "webhook_headers": row["webhook_headers"] or {},
        "enabled": row["enabled"],
        "created_at": row["created_at"].isoformat() if row["created_at"] else None,
    }


@router.get("/soar/playbooks", dependencies=[Depends(require_permission("siem:read"))])
async def list_soar_playbooks(db: AsyncSession = Depends(get_db)):
    await _ensure_siem_tables(db)
    result = await db.execute(text("SELECT * FROM neuranac_soar_playbooks ORDER BY created_at DESC"))
    rows = result.mappings().all()
    items = [_row_to_playbook(r) for r in rows]
    return {"items": items, "total": len(items)}


@router.post("/soar/playbooks", status_code=201, dependencies=[Depends(require_permission("siem:manage"))])
async def create_soar_playbook(req: SOARPlaybook, db: AsyncSession = Depends(get_db)):
    await _ensure_siem_tables(db)
    result = await db.execute(text("""
        INSERT INTO neuranac_soar_playbooks (name, trigger_event, webhook_url, webhook_headers, enabled)
        VALUES (:name, :trigger_event, :webhook_url, CAST(:webhook_headers AS jsonb), :enabled)
        RETURNING *
    """), {
        "name": req.name, "trigger_event": req.trigger_event,
        "webhook_url": req.webhook_url,
        "webhook_headers": json.dumps(req.webhook_headers or {}),
        "enabled": req.enabled,
    })
    await db.commit()
    row = result.mappings().first()
    return _row_to_playbook(row)


@router.post("/soar/playbooks/{playbook_id}/trigger", dependencies=[Depends(require_permission("siem:manage"))])
async def trigger_soar_playbook(playbook_id: str, event: dict = {}, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        text("SELECT * FROM neuranac_soar_playbooks WHERE id = :id"), {"id": playbook_id}
    )
    row = result.mappings().first()
    if not row:
        raise HTTPException(404, "Playbook not found")
    pb = _row_to_playbook(row)
    try:
        import httpx
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                pb["webhook_url"],
                json={"playbook": pb["name"], "event": event, "source": "neuranac",
                      "timestamp": datetime.now(timezone.utc).replace(tzinfo=None).isoformat()},
                headers=pb.get("webhook_headers", {}),
            )
            return {"status": "triggered", "http_status": resp.status_code}
    except Exception as e:
        return {"status": "failed", "error": str(e)}


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _format_cef(vendor: str, event: str, severity: str, msg: str, numeric_sev: int) -> str:
    """Format a CEF (Common Event Format) message per ArcSight spec"""
    ts = datetime.now(timezone.utc).replace(tzinfo=None).strftime("%b %d %Y %H:%M:%S")
    return f"CEF:0|Cisco|{vendor}|1.0|{event}|{event}|{numeric_sev}|msg={msg} rt={ts}"


def _severity_to_cef(severity: str) -> str:
    return {"low": "3", "medium": "5", "high": "7", "critical": "10"}.get(severity, "5")


def _severity_to_int(severity: str) -> int:
    return {"low": 3, "medium": 5, "high": 7, "critical": 10}.get(severity, 5)


def _send_syslog(host: str, port: int, protocol: str, message: str):
    """Send a syslog message via UDP or TCP"""
    encoded = message.encode("utf-8")
    if protocol == "tcp":
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((host, port))
        sock.sendall(encoded + b"\n")
        sock.close()
    else:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.sendto(encoded, (host, port))
        sock.close()
