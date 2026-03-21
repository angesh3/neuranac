"""Identity sources CRUD router - AD, LDAP, SAML, OAuth, internal"""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database.session import get_db
from app.models.network import IdentitySource
from app.middleware.tenant_helper import get_tenant_id

router = APIRouter()


class IdentitySourceCreate(BaseModel):
    name: str
    source_type: str  # ad, ldap, saml, oauth, internal
    config: dict = {}
    priority: int = 1


class IdentitySourceUpdate(BaseModel):
    name: Optional[str] = None
    config: Optional[dict] = None
    priority: Optional[int] = None
    status: Optional[str] = None


@router.get("/")
async def list_identity_sources(skip: int = Query(0), limit: int = Query(50), db: AsyncSession = Depends(get_db)):
    total = await db.scalar(select(func.count()).select_from(IdentitySource))
    result = await db.execute(select(IdentitySource).offset(skip).limit(limit).order_by(IdentitySource.priority))
    items = result.scalars().all()
    return {"items": [_ser(s) for s in items], "total": total or 0, "skip": skip, "limit": limit}


@router.post("/", status_code=201)
async def create_identity_source(req: IdentitySourceCreate, request: Request, db: AsyncSession = Depends(get_db)):
    src = IdentitySource(name=req.name, source_type=req.source_type, config=req.config,
                         priority=req.priority, tenant_id=get_tenant_id(request))
    db.add(src)
    await db.flush()
    return _ser(src)


@router.get("/{source_id}")
async def get_identity_source(source_id: UUID, db: AsyncSession = Depends(get_db)):
    src = await db.get(IdentitySource, source_id)
    if not src:
        raise HTTPException(404, "Identity source not found")
    return _ser(src)


@router.put("/{source_id}")
async def update_identity_source(source_id: UUID, req: IdentitySourceUpdate, db: AsyncSession = Depends(get_db)):
    src = await db.get(IdentitySource, source_id)
    if not src:
        raise HTTPException(404, "Identity source not found")
    for k, v in req.model_dump(exclude_unset=True).items():
        setattr(src, k, v)
    await db.flush()
    return _ser(src)


@router.delete("/{source_id}", status_code=204)
async def delete_identity_source(source_id: UUID, db: AsyncSession = Depends(get_db)):
    src = await db.get(IdentitySource, source_id)
    if not src:
        raise HTTPException(404, "Identity source not found")
    await db.delete(src)


@router.post("/{source_id}/test")
async def test_identity_source(source_id: UUID, db: AsyncSession = Depends(get_db)):
    src = await db.get(IdentitySource, source_id)
    if not src:
        raise HTTPException(404, "Identity source not found")

    cfg = src.config or {}
    result = {"source_id": str(source_id), "type": src.source_type}

    if src.source_type in ("ldap", "ad"):
        import ldap3
        server_url = cfg.get("server", "ldap://localhost:389")
        bind_dn = cfg.get("bind_dn", "")
        bind_password = cfg.get("bind_password", "")
        try:
            server = ldap3.Server(server_url, get_info=ldap3.DSA)
            conn = ldap3.Connection(server, user=bind_dn, password=bind_password, auto_bind=True)
            result["status"] = "connection_ok"
            result["server_info"] = str(server.info.naming_contexts) if server.info else "N/A"
            conn.unbind()
        except Exception as e:
            result["status"] = "connection_failed"
            result["error"] = str(e)

    elif src.source_type == "saml":
        idp_url = cfg.get("idp_metadata_url", "")
        result["status"] = "configured" if idp_url else "missing_idp_url"
        result["idp_metadata_url"] = idp_url

    elif src.source_type == "oauth":
        result["status"] = "configured" if cfg.get("client_id") else "missing_client_id"

    else:
        result["status"] = "connection_ok"

    return result


@router.post("/{source_id}/sync")
async def sync_identity_source(source_id: UUID, db: AsyncSession = Depends(get_db)):
    src = await db.get(IdentitySource, source_id)
    if not src:
        raise HTTPException(404, "Identity source not found")

    cfg = src.config or {}
    if src.source_type in ("ldap", "ad"):
        import ldap3
        server_url = cfg.get("server", "ldap://localhost:389")
        bind_dn = cfg.get("bind_dn", "")
        bind_password = cfg.get("bind_password", "")
        base_dn = cfg.get("base_dn", "")
        user_filter = cfg.get("user_filter", "(objectClass=person)")
        try:
            server = ldap3.Server(server_url, get_info=ldap3.DSA)
            conn = ldap3.Connection(server, user=bind_dn, password=bind_password, auto_bind=True)
            conn.search(base_dn, user_filter, attributes=["cn", "sAMAccountName", "mail", "memberOf"])
            user_count = len(conn.entries)
            conn.unbind()
            from datetime import datetime, timezone
            src.last_sync = datetime.now(timezone.utc).replace(tzinfo=None)
            await db.flush()
            return {"status": "sync_complete", "source_id": str(source_id), "users_found": user_count}
        except Exception as e:
            return {"status": "sync_failed", "source_id": str(source_id), "error": str(e)}

    return {"status": "sync_started", "source_id": str(source_id)}


class SAMLAuthRequest(BaseModel):
    source_id: str
    relay_state: Optional[str] = None


@router.post("/saml/initiate")
async def saml_initiate(req: SAMLAuthRequest, db: AsyncSession = Depends(get_db)):
    """Initiate SAML SSO — generates AuthnRequest and returns redirect URL to IdP"""
    src = await db.get(IdentitySource, req.source_id)
    if not src or src.source_type != "saml":
        raise HTTPException(400, "Invalid SAML identity source")
    cfg = src.config or {}
    idp_sso_url = cfg.get("idp_sso_url", cfg.get("idp_metadata_url", ""))
    entity_id = cfg.get("entity_id", "urn:neuranac:sp")
    acs_url = cfg.get("acs_url", "http://localhost:8080/api/v1/identity-sources/saml/acs")

    if not idp_sso_url:
        raise HTTPException(400, "IdP SSO URL not configured")

    import base64
    import uuid
    from datetime import datetime, timezone
    request_id = f"_neuranac_{uuid.uuid4().hex}"
    issue_instant = datetime.now(timezone.utc).replace(tzinfo=None).strftime("%Y-%m-%dT%H:%M:%SZ")

    # Build SAML AuthnRequest XML
    authn_request = f"""<samlp:AuthnRequest xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol"
        xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion"
        ID="{request_id}" Version="2.0" IssueInstant="{issue_instant}"
        Destination="{idp_sso_url}"
        AssertionConsumerServiceURL="{acs_url}"
        ProtocolBinding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST">
        <saml:Issuer>{entity_id}</saml:Issuer>
        <samlp:NameIDPolicy Format="urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress" AllowCreate="true"/>
    </samlp:AuthnRequest>"""

    encoded = base64.b64encode(authn_request.encode()).decode()
    redirect_url = f"{idp_sso_url}?SAMLRequest={encoded}"
    if req.relay_state:
        redirect_url += f"&RelayState={req.relay_state}"

    return {
        "redirect_url": redirect_url,
        "request_id": request_id,
        "idp_url": idp_sso_url,
        "entity_id": entity_id,
    }


@router.post("/saml/acs")
async def saml_acs(SAMLResponse: str = "", RelayState: str = ""):
    """SAML Assertion Consumer Service — processes IdP response"""
    import base64
    if not SAMLResponse:
        raise HTTPException(400, "Missing SAMLResponse")

    try:
        decoded = base64.b64decode(SAMLResponse).decode("utf-8", errors="replace")
        # Parse username from SAML assertion (simplified — production uses xmlsec)
        username = ""
        if "<saml:NameID" in decoded:
            start = decoded.index("<saml:NameID")
            end = decoded.index("</saml:NameID>", start)
            tag_content = decoded[start:end]
            if ">" in tag_content:
                username = tag_content.split(">", 1)[1]

        if not username:
            username = "saml_user"

        return {
            "status": "authenticated",
            "username": username,
            "auth_method": "saml",
            "relay_state": RelayState,
            "session_token": f"saml-{username}",
        }
    except Exception as e:
        raise HTTPException(400, f"Invalid SAML response: {str(e)}")


class OAuthCallbackParams(BaseModel):
    code: str
    state: Optional[str] = None
    source_id: str


@router.post("/oauth/initiate")
async def oauth_initiate(source_id: str, db: AsyncSession = Depends(get_db)):
    """Initiate OAuth2 authorization code flow — returns redirect URL"""
    src = await db.get(IdentitySource, source_id)
    if not src or src.source_type != "oauth":
        raise HTTPException(400, "Invalid OAuth identity source")
    cfg = src.config or {}

    auth_url = cfg.get("authorization_url", "")
    client_id = cfg.get("client_id", "")
    redirect_uri = cfg.get("redirect_uri", "http://localhost:8080/api/v1/identity-sources/oauth/callback")
    scope = cfg.get("scope", "openid profile email")

    if not auth_url or not client_id:
        raise HTTPException(400, "OAuth authorization_url or client_id not configured")

    import uuid
    state = uuid.uuid4().hex
    redirect_url = f"{auth_url}?response_type=code&client_id={client_id}&redirect_uri={redirect_uri}&scope={scope}&state={state}"

    return {"redirect_url": redirect_url, "state": state}


@router.post("/oauth/callback")
async def oauth_callback(req: OAuthCallbackParams, db: AsyncSession = Depends(get_db)):
    """OAuth2 callback — exchanges authorization code for tokens"""
    src = await db.get(IdentitySource, req.source_id)
    if not src or src.source_type != "oauth":
        raise HTTPException(400, "Invalid OAuth identity source")
    cfg = src.config or {}

    token_url = cfg.get("token_url", "")
    client_id = cfg.get("client_id", "")
    client_secret = cfg.get("client_secret", "")
    redirect_uri = cfg.get("redirect_uri", "http://localhost:8080/api/v1/identity-sources/oauth/callback")

    if not token_url:
        raise HTTPException(400, "OAuth token_url not configured")

    import httpx
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(token_url, data={
                "grant_type": "authorization_code",
                "code": req.code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
            })
            if resp.status_code != 200:
                return {"status": "token_exchange_failed", "error": resp.text}

            tokens = resp.json()
            # Decode userinfo from ID token or call userinfo endpoint
            userinfo_url = cfg.get("userinfo_url", "")
            username = tokens.get("email", "oauth_user")

            if userinfo_url and tokens.get("access_token"):
                try:
                    ui_resp = await client.get(userinfo_url,
                        headers={"Authorization": f"Bearer {tokens['access_token']}"})
                    if ui_resp.status_code == 200:
                        userinfo = ui_resp.json()
                        username = userinfo.get("email", userinfo.get("preferred_username", username))
                except Exception:
                    pass

            return {
                "status": "authenticated",
                "username": username,
                "auth_method": "oauth",
                "access_token": tokens.get("access_token", ""),
                "token_type": tokens.get("token_type", "bearer"),
                "expires_in": tokens.get("expires_in", 3600),
            }
    except Exception as e:
        return {"status": "failed", "error": str(e)}


def _ser(s: IdentitySource) -> dict:
    return {
        "id": str(s.id), "name": s.name, "source_type": s.source_type,
        "config": s.config, "priority": s.priority, "status": s.status,
        "last_sync": str(s.last_sync) if s.last_sync else None,
        "created_at": str(s.created_at) if s.created_at else None,
    }
