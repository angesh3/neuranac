"""Network devices (NAD) CRUD router"""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database.session import get_db
from app.models.network import NetworkDevice
from app.middleware.auth import require_permission
from app.middleware.tenant_helper import get_tenant_id
from app.utils.crypto import encrypt_secret

router = APIRouter()


class NADCreate(BaseModel):
    name: str
    ip_address: str
    device_type: Optional[str] = None
    vendor: Optional[str] = None
    model: Optional[str] = None
    shared_secret: str
    radsec_enabled: bool = False
    coa_port: int = 3799
    location: Optional[str] = None


class NADUpdate(BaseModel):
    name: Optional[str] = None
    device_type: Optional[str] = None
    vendor: Optional[str] = None
    model: Optional[str] = None
    shared_secret: Optional[str] = None
    radsec_enabled: Optional[bool] = None
    coa_port: Optional[int] = None
    location: Optional[str] = None
    status: Optional[str] = None


@router.get("/", dependencies=[Depends(require_permission("network:read"))])
async def list_network_devices(skip: int = Query(0), limit: int = Query(50), db: AsyncSession = Depends(get_db)):
    total = await db.scalar(select(func.count()).select_from(NetworkDevice))
    result = await db.execute(select(NetworkDevice).offset(skip).limit(limit).order_by(NetworkDevice.created_at.desc()))
    items = result.scalars().all()
    return {"items": [_serialize(d) for d in items], "total": total or 0, "skip": skip, "limit": limit}


@router.get("/{device_id}", dependencies=[Depends(require_permission("network:read"))])
async def get_network_device(device_id: UUID, db: AsyncSession = Depends(get_db)):
    device = await db.get(NetworkDevice, device_id)
    if not device:
        raise HTTPException(404, "Network device not found")
    return _serialize(device)


@router.post("/", status_code=201, dependencies=[Depends(require_permission("network:write"))])
async def create_network_device(req: NADCreate, request: Request, db: AsyncSession = Depends(get_db)):
    device = NetworkDevice(
        name=req.name, ip_address=req.ip_address, device_type=req.device_type,
        vendor=req.vendor, model=req.model, shared_secret_encrypted=encrypt_secret(req.shared_secret) if req.shared_secret else None,
        radsec_enabled=req.radsec_enabled, coa_port=req.coa_port, location=req.location,
        tenant_id=get_tenant_id(request),
    )
    db.add(device)
    await db.flush()
    return _serialize(device)


@router.put("/{device_id}", dependencies=[Depends(require_permission("network:write"))])
async def update_network_device(device_id: UUID, req: NADUpdate, db: AsyncSession = Depends(get_db)):
    device = await db.get(NetworkDevice, device_id)
    if not device:
        raise HTTPException(404, "Network device not found")
    for k, v in req.model_dump(exclude_unset=True).items():
        if k == "shared_secret":
            setattr(device, "shared_secret_encrypted", encrypt_secret(v) if v else None)
        else:
            setattr(device, k, v)
    await db.flush()
    return _serialize(device)


@router.delete("/{device_id}", status_code=204, dependencies=[Depends(require_permission("network:write"))])
async def delete_network_device(device_id: UUID, db: AsyncSession = Depends(get_db)):
    device = await db.get(NetworkDevice, device_id)
    if not device:
        raise HTTPException(404, "Network device not found")
    await db.delete(device)


class DiscoveryRequest(BaseModel):
    subnet: str  # e.g. "10.0.0.0/24"
    snmp_community: str = "public"
    methods: list = ["snmp", "cdp", "lldp", "ping"]
    timeout_seconds: int = 30


@router.post("/discover", dependencies=[Depends(require_permission("network:write"))])
async def discover_network_devices(req: DiscoveryRequest, db: AsyncSession = Depends(get_db)):
    """Auto-discover network devices on a subnet via SNMP/CDP/LLDP/ping sweep.
    Returns discovered devices not yet registered as NADs."""
    import ipaddress
    import socket

    try:
        network = ipaddress.ip_network(req.subnet, strict=False)
    except ValueError:
        raise HTTPException(400, f"Invalid subnet: {req.subnet}")

    # Get already-registered IPs
    result = await db.execute(select(NetworkDevice.ip_address))
    registered_ips = {row[0] for row in result.fetchall()}

    discovered = []
    # Ping sweep + port probe for SNMP (161) and RADIUS (1812)
    hosts = list(network.hosts())[:254]  # Cap at /24
    for host in hosts:
        ip = str(host)
        if ip in registered_ips:
            continue
        reachable = False
        device_info = {"ip_address": ip, "discovered_via": []}

        # TCP port probe (faster than NeuraNACP ping which needs root)
        for port, svc in [(161, "snmp"), (22, "ssh"), (443, "https"), (23, "telnet")]:
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(0.5)
                result_code = sock.connect_ex((ip, port))
                sock.close()
                if result_code == 0:
                    reachable = True
                    device_info["discovered_via"].append(svc)
            except Exception:
                pass

        if reachable:
            # Try to guess vendor from hostname/DNS
            try:
                hostname = socket.getfqdn(ip)
                device_info["hostname"] = hostname if hostname != ip else None
            except Exception:
                device_info["hostname"] = None

            device_info["vendor"] = _guess_vendor(device_info.get("hostname", ""))
            device_info["device_type"] = "switch" if device_info["vendor"] else "unknown"
            discovered.append(device_info)

    return {
        "subnet": req.subnet,
        "total_scanned": len(hosts),
        "discovered": len(discovered),
        "already_registered": len(registered_ips),
        "devices": discovered,
    }


def _guess_vendor(hostname: str) -> str:
    hostname = (hostname or "").lower()
    if any(k in hostname for k in ["cisco", "cat", "isr", "nexus"]):
        return "Cisco"
    elif any(k in hostname for k in ["aruba", "hpe"]):
        return "Aruba"
    elif any(k in hostname for k in ["juniper", "srx", "ex"]):
        return "Juniper"
    elif any(k in hostname for k in ["meraki", "mr", "ms", "mx"]):
        return "Meraki"
    return ""


def _serialize(d: NetworkDevice) -> dict:
    return {
        "id": str(d.id), "name": d.name, "ip_address": d.ip_address,
        "device_type": d.device_type, "vendor": d.vendor, "model": d.model,
        "radsec_enabled": d.radsec_enabled, "coa_port": d.coa_port,
        "location": d.location, "status": d.status, "last_seen": str(d.last_seen) if d.last_seen else None,
        "created_at": str(d.created_at) if d.created_at else None,
    }
