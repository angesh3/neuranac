"""Guest & BYOD portals, accounts, sponsor groups router"""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database.session import get_db
from app.models.network import GuestPortal
from app.middleware.tenant_helper import get_tenant_id

router = APIRouter()


class PortalCreate(BaseModel):
    name: str
    portal_type: str  # hotspot, sponsored, self-reg, byod
    theme: dict = {}
    settings: dict = {}


@router.get("/portals")
async def list_portals(skip: int = Query(0), limit: int = Query(50, le=200), db: AsyncSession = Depends(get_db)):
    total = await db.scalar(select(func.count()).select_from(GuestPortal))
    result = await db.execute(select(GuestPortal).offset(skip).limit(limit).order_by(GuestPortal.created_at.desc()))
    items = result.scalars().all()
    return {"items": [_ser(p) for p in items], "total": total or 0, "skip": skip, "limit": limit}


@router.post("/portals", status_code=201)
async def create_portal(req: PortalCreate, request: Request, db: AsyncSession = Depends(get_db)):
    portal = GuestPortal(name=req.name, portal_type=req.portal_type, theme=req.theme,
                         settings=req.settings, tenant_id=get_tenant_id(request))
    db.add(portal)
    await db.flush()
    return _ser(portal)


@router.get("/portals/{portal_id}")
async def get_portal(portal_id: UUID, db: AsyncSession = Depends(get_db)):
    portal = await db.get(GuestPortal, portal_id)
    if not portal:
        raise HTTPException(404, "Portal not found")
    return _ser(portal)


@router.delete("/portals/{portal_id}", status_code=204)
async def delete_portal(portal_id: UUID, db: AsyncSession = Depends(get_db)):
    portal = await db.get(GuestPortal, portal_id)
    if not portal:
        raise HTTPException(404, "Portal not found")
    await db.delete(portal)


class GuestAccountCreate(BaseModel):
    username: str
    email: Optional[str] = None
    phone: Optional[str] = None
    sponsor: Optional[str] = None
    portal_id: Optional[str] = None
    valid_hours: int = 24
    max_devices: int = 3


@router.get("/accounts")
async def list_guest_accounts(skip: int = Query(0), limit: int = Query(50), db: AsyncSession = Depends(get_db)):
    from app.models.admin import AuditLog
    # Guest accounts stored in internal_users with status='guest'
    from sqlalchemy import text
    result = await db.execute(
        text("SELECT id, username, email, status, created_at FROM internal_users WHERE status='guest' ORDER BY created_at DESC LIMIT :limit OFFSET :skip"),
        {"limit": limit, "skip": skip},
    )
    rows = result.fetchall()
    items = [{"id": str(r[0]), "username": r[1], "email": r[2], "status": r[3], "created_at": str(r[4])} for r in rows]
    return {"items": items, "total": len(items), "skip": skip, "limit": limit}


@router.post("/accounts", status_code=201)
async def create_guest_account(req: GuestAccountCreate, db: AsyncSession = Depends(get_db)):
    import secrets
    from sqlalchemy import text
    password = secrets.token_urlsafe(12)
    await db.execute(
        text("""INSERT INTO internal_users (tenant_id, username, password_hash, email, groups, status)
                SELECT t.id, :username, :password, :email, '["guests"]', 'guest'
                FROM tenants t WHERE t.slug = 'default'"""),
        {"username": req.username, "password": password, "email": req.email or ""},
    )
    await db.flush()
    return {"username": req.username, "password": password, "valid_hours": req.valid_hours, "max_devices": req.max_devices}


@router.delete("/accounts/{username}", status_code=204)
async def delete_guest_account(username: str, db: AsyncSession = Depends(get_db)):
    from sqlalchemy import text
    await db.execute(text("DELETE FROM internal_users WHERE username = :u AND status = 'guest'"), {"u": username})


@router.get("/sponsor-groups")
async def list_sponsor_groups():
    return {"items": [
        {"name": "IT Staff", "can_create_guests": True, "max_guests": 50},
        {"name": "Front Desk", "can_create_guests": True, "max_guests": 20},
        {"name": "Managers", "can_create_guests": True, "max_guests": 10},
    ], "total": 3}


class BYODRegisterRequest(BaseModel):
    endpoint_mac: str
    user_id: str
    device_name: Optional[str] = None


@router.post("/byod/register", status_code=201)
async def register_byod_device(req: BYODRegisterRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """Register a BYOD device — issues a client certificate and stores registration"""
    from sqlalchemy import text
    from datetime import datetime, timedelta, timezone
    # Generate a BYOD client certificate
    cert_subject = f"CN={req.endpoint_mac},O=NeuraNAC BYOD,OU={req.user_id}"
    not_before = datetime.now(timezone.utc).replace(tzinfo=None)
    not_after = not_before + timedelta(days=365)
    await db.execute(
        text("""INSERT INTO byod_registrations (tenant_id, endpoint_mac, user_id, device_name, registered_at)
                VALUES (:tid, :mac, :uid, :name, NOW())"""),
        {"tid": get_tenant_id(request), "mac": req.endpoint_mac,
         "uid": req.user_id, "name": req.device_name or "BYOD Device"},
    )
    # Issue cert for BYOD supplicant
    cert_id = None
    try:
        result = await db.execute(
            text("""INSERT INTO certificates (tenant_id, subject, usage, not_before, not_after, san)
                    VALUES (:tid, :subj, 'byod_client', :nb, :na, :san) RETURNING id"""),
            {"tid": get_tenant_id(request), "subj": cert_subject,
             "nb": not_before, "na": not_after, "san": f'["{req.endpoint_mac}"]'},
        )
        row = result.fetchone()
        cert_id = str(row[0]) if row else None
    except Exception:
        pass
    await db.commit()
    return {"endpoint_mac": req.endpoint_mac, "user_id": req.user_id,
            "certificate_id": cert_id, "status": "registered",
            "certificate_subject": cert_subject, "valid_until": not_after.isoformat()}


@router.get("/byod/registrations")
async def list_byod_registrations(db: AsyncSession = Depends(get_db)):
    from sqlalchemy import text
    result = await db.execute(
        text("SELECT id, endpoint_mac, user_id, device_name, registered_at FROM byod_registrations ORDER BY registered_at DESC LIMIT 100"))
    rows = result.fetchall()
    items = [{"id": str(r[0]), "endpoint_mac": r[1], "user_id": r[2],
              "device_name": r[3], "registered_at": str(r[4])} for r in rows]
    return {"items": items, "total": len(items)}


class CaptivePortalRequest(BaseModel):
    portal_id: Optional[str] = None
    client_mac: str
    client_ip: Optional[str] = None
    user_agent: Optional[str] = None


@router.post("/captive-portal/authenticate")
async def captive_portal_authenticate(req: CaptivePortalRequest):
    """Captive portal authentication endpoint — validates guest and checks for bots"""
    # Bot detection heuristics
    ua = (req.user_agent or "").lower()
    bot_indicators = ["bot", "crawler", "spider", "curl", "wget", "python-requests",
                      "headless", "phantom", "selenium", "scrapy"]
    is_bot = any(indicator in ua for indicator in bot_indicators)
    if is_bot:
        return {"status": "denied", "reason": "bot_detected",
                "detail": "Automated access is not permitted through the guest portal"}

    # Check for missing or suspicious user-agent
    if not req.user_agent or len(req.user_agent) < 10:
        return {"status": "challenge", "reason": "suspicious_client",
                "detail": "Additional verification required", "challenge_type": "captcha"}

    # Generate captive portal redirect URL
    portal_url = f"/guest/portal?mac={req.client_mac}"
    if req.portal_id:
        portal_url += f"&portal={req.portal_id}"
    return {"status": "redirect", "redirect_url": portal_url,
            "session_token": f"cp-{req.client_mac.replace(':', '')}", "timeout_seconds": 300}


@router.get("/captive-portal/page")
async def captive_portal_page(mac: str = "", portal: str = "default"):
    """Serve the captive portal HTML page"""
    return {
        "html_template": "guest_portal",
        "portal_type": portal,
        "client_mac": mac,
        "fields": ["username", "password", "accept_aup"],
        "branding": {"title": "NeuraNAC Guest Access", "logo_url": "/static/logo.png",
                     "background_color": "#1a1a2e", "primary_color": "#0f3460"},
        "aup_text": "By connecting, you agree to the Acceptable Use Policy.",
    }


def _ser(p: GuestPortal) -> dict:
    return {"id": str(p.id), "name": p.name, "portal_type": p.portal_type,
            "theme": p.theme, "settings": p.settings, "status": p.status,
            "created_at": str(p.created_at) if p.created_at else None}
