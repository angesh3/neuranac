"""Certificates and CAs CRUD router"""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database.session import get_db
from app.models.network import Certificate, CertificateAuthority
from app.middleware.auth import require_permission
from app.middleware.tenant_helper import get_tenant_id

router = APIRouter()


class CACreate(BaseModel):
    name: str
    ca_type: str  # root, intermediate, external
    subject: Optional[str] = None


class CertCreate(BaseModel):
    ca_id: Optional[str] = None
    subject: str
    usage: str = "eap-tls"
    san: list = []


@router.get("/cas", dependencies=[Depends(require_permission("cert:read"))])
async def list_cas(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(CertificateAuthority).order_by(CertificateAuthority.created_at.desc()))
    items = result.scalars().all()
    return {"items": [_ser_ca(c) for c in items], "total": len(items)}


@router.post("/cas", status_code=201, dependencies=[Depends(require_permission("cert:manage"))])
async def create_ca(req: CACreate, request: Request, db: AsyncSession = Depends(get_db)):
    ca = CertificateAuthority(name=req.name, ca_type=req.ca_type, subject=req.subject,
                              tenant_id=get_tenant_id(request))
    db.add(ca)
    await db.flush()
    return _ser_ca(ca)


@router.get("/", dependencies=[Depends(require_permission("cert:read"))])
async def list_certificates(skip: int = Query(0), limit: int = Query(50), db: AsyncSession = Depends(get_db)):
    total = await db.scalar(select(func.count()).select_from(Certificate))
    result = await db.execute(select(Certificate).offset(skip).limit(limit).order_by(Certificate.created_at.desc()))
    items = result.scalars().all()
    return {"items": [_ser_cert(c) for c in items], "total": total or 0, "skip": skip, "limit": limit}


@router.post("/", status_code=201, dependencies=[Depends(require_permission("cert:manage"))])
async def create_certificate(req: CertCreate, request: Request, db: AsyncSession = Depends(get_db)):
    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from datetime import datetime, timedelta, timezone
    import uuid as _uuid

    # Generate RSA key pair
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    serial = x509.random_serial_number()

    # Build subject
    subject = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, req.subject),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, "NeuraNAC"),
    ])

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    builder = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)  # self-signed; in production, use CA
        .public_key(key.public_key())
        .serial_number(serial)
        .not_valid_before(now)
        .not_valid_after(now + timedelta(days=365))
    )

    # Add SANs
    san_list = []
    for s in (req.san or []):
        if s.startswith("*.") or "." in s:
            san_list.append(x509.DNSName(s))
        else:
            san_list.append(x509.DNSName(s))
    if san_list:
        builder = builder.add_extension(x509.SubjectAlternativeName(san_list), critical=False)

    # Self-sign
    certificate = builder.sign(key, hashes.SHA256())

    cert_pem = certificate.public_bytes(serialization.Encoding.PEM).decode()

    cert_obj = Certificate(
        subject=req.subject, usage=req.usage, san=req.san,
        serial=format(serial, 'x'),
        not_before=now, not_after=now + timedelta(days=365),
        cert_pem=cert_pem,
        tenant_id=get_tenant_id(request),
    )
    db.add(cert_obj)
    await db.flush()
    return _ser_cert(cert_obj)


@router.get("/{cert_id}", dependencies=[Depends(require_permission("cert:read"))])
async def get_certificate(cert_id: UUID, db: AsyncSession = Depends(get_db)):
    cert = await db.get(Certificate, cert_id)
    if not cert:
        raise HTTPException(404, "Certificate not found")
    return _ser_cert(cert)


@router.post("/{cert_id}/revoke", dependencies=[Depends(require_permission("cert:manage"))])
async def revoke_certificate(cert_id: UUID, db: AsyncSession = Depends(get_db)):
    cert = await db.get(Certificate, cert_id)
    if not cert:
        raise HTTPException(404, "Certificate not found")
    cert.revoked = True
    from datetime import datetime, timezone
    cert.revoked_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.flush()
    return {"status": "revoked", "cert_id": str(cert_id)}


def _ser_ca(c: CertificateAuthority) -> dict:
    return {"id": str(c.id), "name": c.name, "ca_type": c.ca_type, "subject": c.subject,
            "status": c.status, "not_before": str(c.not_before) if c.not_before else None,
            "not_after": str(c.not_after) if c.not_after else None}


def _ser_cert(c: Certificate) -> dict:
    return {"id": str(c.id), "subject": c.subject, "serial": c.serial,
            "usage": c.usage, "san": c.san, "revoked": c.revoked,
            "not_before": str(c.not_before) if c.not_before else None,
            "not_after": str(c.not_after) if c.not_after else None,
            "created_at": str(c.created_at) if c.created_at else None}
