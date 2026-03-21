"""Zero-Trust Activation Code Router — secure on-prem connector bootstrap.

Flow:
  1. Cloud admin: POST /api/v1/connectors/activation-codes → generates code (e.g. NeuraNAC-A3F9-K7M2)
  2. On-prem: POST /api/v1/connectors/activate {code} → returns site config + shared secret
  3. Code is consumed (single-use, 24h TTL)
  4. Connector self-configures and registers securely

Security:
  - Activation codes are 8-char alphanumeric with NeuraNAC- prefix (e.g. NeuraNAC-XXXX-YYYY)
  - Single-use: consumed on first activate call
  - 24-hour TTL by default (configurable)
  - Generation requires admin:manage permission
  - Activation endpoint is unauthenticated (the code IS the credential)
"""
import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
import structlog

from app.config import get_settings
from app.database.session import get_db
from app.middleware.auth import require_permission
from app.middleware.tenant_helper import get_tenant_id

logger = structlog.get_logger()
router = APIRouter()

DEFAULT_CODE_TTL_HOURS = 24


# ─── Models ──────────────────────────────────────────────────────────────────

class ActivationCodeCreate(BaseModel):
    site_id: str
    connector_type: str = "legacy_nac"
    ttl_hours: int = Field(default=DEFAULT_CODE_TTL_HOURS, ge=1, le=168)
    metadata: dict = {}


class ActivationCodeResponse(BaseModel):
    id: str
    code: str
    site_id: str
    connector_type: str
    status: str
    expires_at: str
    created_at: str


class ActivateRequest(BaseModel):
    code: str
    connector_name: Optional[str] = "neuranac-bridge"
    legacy_nac_hostname: Optional[str] = None


class ActivateResponse(BaseModel):
    connector_id: str
    site_id: str
    site_name: str
    cloud_api_url: str
    cloud_ws_url: str
    federation_secret: str
    status: str
    mtls: Optional[dict] = None


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _generate_activation_code() -> str:
    """Generate a human-readable activation code: NeuraNAC-XXXX-YYYY."""
    chars = string.ascii_uppercase + string.digits
    # Remove ambiguous characters (0/O, 1/I/L)
    chars = chars.replace("O", "").replace("0", "").replace("I", "").replace("L", "").replace("1", "")
    part1 = "".join(secrets.choice(chars) for _ in range(4))
    part2 = "".join(secrets.choice(chars) for _ in range(4))
    return f"NeuraNAC-{part1}-{part2}"


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.post("/activation-codes", status_code=201,
             dependencies=[Depends(require_permission("admin:manage"))])
async def create_activation_code(
    body: ActivationCodeCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Generate a single-use activation code for on-prem connector bootstrap.

    The admin shares this code with the on-prem installer. The code is valid
    for ttl_hours (default 24h) and can only be used once.
    """
    settings = get_settings()
    tid = get_tenant_id(request)
    if not settings.legacy_nac_enabled and body.connector_type == "legacy_nac":
        raise HTTPException(400, "NeuraNAC is not enabled on this deployment")

    # Verify site exists and belongs to tenant
    site = await db.execute(
        text("SELECT id, name FROM neuranac_sites WHERE id = :sid AND tenant_id = :tid"),
        {"sid": body.site_id, "tid": tid},
    )
    site_row = site.fetchone()
    if not site_row:
        raise HTTPException(404, f"Site {body.site_id} not found for this tenant")

    code = _generate_activation_code()
    expires = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=body.ttl_hours)

    # Get creating user from request state
    user_id = getattr(request.state, "user_id", None)

    result = await db.execute(text(
        "INSERT INTO neuranac_activation_codes "
        "(tenant_id, code, site_id, connector_type, created_by, expires_at, metadata) "
        "VALUES (:tid, :code, :sid, :ct, :uid, :exp, :meta) RETURNING id, created_at"
    ), {
        "tid": tid,
        "code": code,
        "sid": body.site_id,
        "ct": body.connector_type,
        "uid": user_id,
        "exp": expires,
        "meta": str(body.metadata),
    })
    await db.commit()
    row = result.fetchone()

    logger.info("Activation code generated",
                code=code, site_id=body.site_id, expires=str(expires))

    return ActivationCodeResponse(
        id=str(row[0]),
        code=code,
        site_id=body.site_id,
        connector_type=body.connector_type,
        status="active",
        expires_at=expires.isoformat(),
        created_at=row[1].isoformat() if row[1] else datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
    )


@router.get("/activation-codes",
            dependencies=[Depends(require_permission("admin:manage"))])
async def list_activation_codes(request: Request, db: AsyncSession = Depends(get_db)):
    """List all activation codes for the current tenant."""
    tid = get_tenant_id(request)
    result = await db.execute(text(
        "SELECT a.id, a.code, a.site_id, a.connector_type, a.status, "
        "a.expires_at, a.consumed_at, a.created_at, s.site_name as site_name "
        "FROM neuranac_activation_codes a "
        "JOIN neuranac_sites s ON a.site_id = s.id "
        "WHERE a.tenant_id = :tid "
        "ORDER BY a.created_at DESC"
    ), {"tid": tid})
    rows = result.fetchall()
    items = []
    for r in rows:
        # Auto-expire codes past TTL
        status = r[4]
        if status == "active" and r[5] and r[5].replace(tzinfo=timezone.utc) < datetime.now(timezone.utc).replace(tzinfo=None):
            status = "expired"
        items.append({
            "id": str(r[0]),
            "code": r[1] if status == "active" else f"{r[1][:8]}****",
            "site_id": str(r[2]),
            "connector_type": r[3],
            "status": status,
            "expires_at": r[5].isoformat() if r[5] else None,
            "consumed_at": r[6].isoformat() if r[6] else None,
            "created_at": r[7].isoformat() if r[7] else None,
            "site_name": r[8],
        })
    return {"items": items, "total": len(items)}


@router.delete("/activation-codes/{code_id}",
               dependencies=[Depends(require_permission("admin:manage"))])
async def revoke_activation_code(code_id: str, db: AsyncSession = Depends(get_db)):
    """Revoke an activation code (prevents future use)."""
    result = await db.execute(
        text("UPDATE neuranac_activation_codes SET status = 'revoked' "
             "WHERE id = :cid AND status = 'active' RETURNING id"),
        {"cid": code_id},
    )
    await db.commit()
    if not result.fetchone():
        raise HTTPException(404, "Active activation code not found")
    return {"id": code_id, "status": "revoked"}


@router.post("/activate")
async def activate_connector(body: ActivateRequest, db: AsyncSession = Depends(get_db)):
    """Called by on-prem Bridge Connector to activate using a one-time code.

    This endpoint is intentionally UNAUTHENTICATED — the activation code
    serves as the credential. On success:
      1. The code is consumed (cannot be reused)
      2. A new connector record is created
      3. The response contains all config needed for the connector to self-configure

    The on-prem connector uses this response to:
      - Set its site_id, cloud_api_url, cloud_ws_url
      - Establish the federation shared secret for HMAC-signed communication
      - Start registration + heartbeat loop
    """
    settings = get_settings()
    code = body.code.strip().upper()

    # Look up the activation code
    result = await db.execute(text(
        "SELECT a.id, a.site_id, a.connector_type, a.status, a.expires_at, "
        "s.site_name as site_name, s.grpc_address as site_api_url "
        "FROM neuranac_activation_codes a "
        "JOIN neuranac_sites s ON a.site_id = s.id "
        "WHERE a.code = :code"
    ), {"code": code})
    row = result.fetchone()

    if not row:
        logger.warning("Activation attempt with invalid code", code=code[:8])
        raise HTTPException(403, "Invalid activation code")

    code_id, site_id, connector_type, status, expires_at, site_name, site_api_url = row

    # Check status
    if status == "consumed":
        raise HTTPException(410, "Activation code has already been used")
    if status == "revoked":
        raise HTTPException(403, "Activation code has been revoked")
    if status == "expired" or (expires_at and expires_at.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc).replace(tzinfo=None)):
        raise HTTPException(410, "Activation code has expired")

    # Resolve tenant_id from the activation code's site
    tenant_result = await db.execute(text(
        "SELECT tenant_id FROM neuranac_sites WHERE id = :sid"
    ), {"sid": str(site_id)})
    t_row = tenant_result.fetchone()
    act_tenant_id = str(t_row[0]) if t_row and t_row[0] else "00000000-0000-0000-0000-000000000000"

    # Create connector record
    connector_result = await db.execute(text(
        "INSERT INTO neuranac_connectors (tenant_id, site_id, connector_type, name, legacy_nac_hostname, status, last_heartbeat) "
        "VALUES (:tid, :sid, :ct, :name, :host, 'registering', now()) RETURNING id"
    ), {
        "tid": act_tenant_id,
        "sid": str(site_id),
        "ct": connector_type,
        "name": body.connector_name or "neuranac-bridge",
        "host": body.legacy_nac_hostname,
    })
    connector_row = connector_result.fetchone()
    connector_id = str(connector_row[0])

    # Consume the activation code
    await db.execute(text(
        "UPDATE neuranac_activation_codes SET status = 'consumed', consumed_by = :cid, consumed_at = now() "
        "WHERE id = :aid"
    ), {"cid": connector_id, "aid": str(code_id)})
    await db.commit()

    # Issue mTLS client certificate for zero-trust communication
    mtls_data = None
    try:
        from app.services.tenant_cert_issuer import TenantCertIssuer
        issuer = TenantCertIssuer(db)
        mtls_data = await issuer.issue_connector_cert(
            tenant_id=act_tenant_id,
            connector_id=connector_id,
            connector_name=body.connector_name or "neuranac-bridge",
        )
    except Exception as e:
        logger.warning("mTLS cert issuance failed (non-fatal)", error=str(e))

    # Build the cloud URLs for the connector
    cloud_api_url = site_api_url or f"http://{settings.api_host}:{settings.api_port}"
    cloud_ws_url = cloud_api_url.replace("http://", "ws://").replace("https://", "wss://")
    cloud_ws_url = f"{cloud_ws_url}/api/v1/ws/connector"

    logger.info("Connector activated via code",
                connector_id=connector_id, site_id=str(site_id),
                code=code[:8] + "****",
                mtls_issued=mtls_data is not None)

    return ActivateResponse(
        connector_id=connector_id,
        site_id=str(site_id),
        site_name=site_name,
        cloud_api_url=cloud_api_url,
        cloud_ws_url=cloud_ws_url,
        federation_secret=settings.federation_shared_secret,
        status="activated",
        mtls=mtls_data,
    )
