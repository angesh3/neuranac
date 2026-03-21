"""Endpoints CRUD router"""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database.session import get_db
from app.models.network import Endpoint
from app.middleware.tenant_helper import get_tenant_id

router = APIRouter()


class EndpointCreate(BaseModel):
    mac_address: str
    device_type: Optional[str] = None
    vendor: Optional[str] = None
    os: Optional[str] = None
    hostname: Optional[str] = None
    ip_address: Optional[str] = None
    attributes: Optional[dict] = None


class EndpointUpdate(BaseModel):
    device_type: Optional[str] = None
    vendor: Optional[str] = None
    os: Optional[str] = None
    hostname: Optional[str] = None
    status: Optional[str] = None
    attributes: Optional[dict] = None


@router.get("/")
async def list_endpoints(
    skip: int = Query(0), limit: int = Query(50),
    device_type: Optional[str] = None, status: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(Endpoint)
    cq = select(func.count()).select_from(Endpoint)
    if device_type:
        q = q.where(Endpoint.device_type == device_type)
        cq = cq.where(Endpoint.device_type == device_type)
    if status:
        q = q.where(Endpoint.status == status)
        cq = cq.where(Endpoint.status == status)
    total = await db.scalar(cq)
    result = await db.execute(q.offset(skip).limit(limit).order_by(Endpoint.last_seen.desc()))
    items = result.scalars().all()
    return {"items": [_serialize(e) for e in items], "total": total or 0, "skip": skip, "limit": limit}


@router.get("/{endpoint_id}")
async def get_endpoint(endpoint_id: UUID, db: AsyncSession = Depends(get_db)):
    ep = await db.get(Endpoint, endpoint_id)
    if not ep:
        raise HTTPException(404, "Endpoint not found")
    return _serialize(ep)


@router.post("/", status_code=201)
async def create_endpoint(req: EndpointCreate, request: Request, db: AsyncSession = Depends(get_db)):
    ep = Endpoint(
        mac_address=req.mac_address, device_type=req.device_type, vendor=req.vendor,
        os=req.os, hostname=req.hostname, ip_address=req.ip_address,
        attributes=req.attributes or {},
        tenant_id=get_tenant_id(request),
    )
    db.add(ep)
    await db.flush()
    return _serialize(ep)


@router.put("/{endpoint_id}")
async def update_endpoint(endpoint_id: UUID, req: EndpointUpdate, db: AsyncSession = Depends(get_db)):
    ep = await db.get(Endpoint, endpoint_id)
    if not ep:
        raise HTTPException(404, "Endpoint not found")
    for k, v in req.model_dump(exclude_unset=True).items():
        setattr(ep, k, v)
    await db.flush()
    return _serialize(ep)


@router.delete("/{endpoint_id}", status_code=204)
async def delete_endpoint(endpoint_id: UUID, db: AsyncSession = Depends(get_db)):
    ep = await db.get(Endpoint, endpoint_id)
    if not ep:
        raise HTTPException(404, "Endpoint not found")
    await db.delete(ep)


@router.post("/{endpoint_id}/profile")
async def profile_endpoint(endpoint_id: UUID, db: AsyncSession = Depends(get_db)):
    """Trigger AI profiling for an endpoint via the AI Engine"""
    ep = await db.get(Endpoint, endpoint_id)
    if not ep:
        raise HTTPException(404, "Endpoint not found")
    import httpx
    from app.config import get_settings
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"http://{settings.ai_engine_host}:{settings.ai_engine_port}/api/v1/profile",
                json={
                    "mac_address": ep.mac_address,
                    "tenant_id": str(ep.tenant_id),
                    "oui_vendor": ep.vendor or "",
                    "dhcp_attributes": ep.attributes.get("dhcp", {}) if ep.attributes else {},
                },
            )
            profile = resp.json()
            ep.device_type = profile.get("device_type", ep.device_type)
            ep.vendor = profile.get("vendor", ep.vendor)
            ep.os = profile.get("os", ep.os)
            await db.flush()
            return {"endpoint_id": str(endpoint_id), "profile": profile}
    except Exception as e:
        return {"endpoint_id": str(endpoint_id), "error": str(e), "status": "profiling_failed"}


@router.get("/by-mac/{mac_address}")
async def get_endpoint_by_mac(mac_address: str, db: AsyncSession = Depends(get_db)):
    """Look up endpoint by MAC address"""
    result = await db.execute(select(Endpoint).where(Endpoint.mac_address == mac_address))
    ep = result.scalar_one_or_none()
    if not ep:
        raise HTTPException(404, "Endpoint not found")
    return _serialize(ep)


def _serialize(e: Endpoint) -> dict:
    return {
        "id": str(e.id), "mac_address": e.mac_address, "device_type": e.device_type,
        "vendor": e.vendor, "os": e.os, "hostname": e.hostname, "ip_address": e.ip_address,
        "status": e.status, "attributes": e.attributes,
        "first_seen": str(e.first_seen) if e.first_seen else None,
        "last_seen": str(e.last_seen) if e.last_seen else None,
    }
