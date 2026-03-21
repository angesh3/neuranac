"""Privacy API router - GDPR/CCPA subject rights, consent, data exports"""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database.session import get_db
from app.models.network import PrivacySubject, PrivacyDataExport, PrivacyConsentRecord
from app.middleware.auth import require_permission
from app.middleware.tenant_helper import get_tenant_id

router = APIRouter()


class SubjectCreate(BaseModel):
    subject_type: str  # user, guest, endpoint
    subject_identifier: str
    consent_given: bool = False
    consent_method: Optional[str] = None
    data_categories: List[str] = []


class ConsentCreate(BaseModel):
    subject_id: str
    purpose: str
    legal_basis: str  # consent, legitimate_interest, contract, legal_obligation
    granted: bool


class DataExportRequest(BaseModel):
    subject_id: str
    requested_by: str
    export_format: str = "json"


# --- Subjects ---

@router.get("/subjects", dependencies=[Depends(require_permission("privacy:read"))])
async def list_subjects(skip: int = Query(0), limit: int = Query(50), db: AsyncSession = Depends(get_db)):
    total = await db.scalar(select(func.count()).select_from(PrivacySubject))
    result = await db.execute(select(PrivacySubject).offset(skip).limit(limit).order_by(PrivacySubject.created_at.desc()))
    items = result.scalars().all()
    return {"items": [_ser_subject(s) for s in items], "total": total or 0}


@router.post("/subjects", status_code=201, dependencies=[Depends(require_permission("privacy:manage"))])
async def create_subject(req: SubjectCreate, request: Request, db: AsyncSession = Depends(get_db)):
    from datetime import datetime, timezone
    subj = PrivacySubject(
        subject_type=req.subject_type, subject_identifier=req.subject_identifier,
        consent_given=req.consent_given, consent_method=req.consent_method,
        consent_date=datetime.now(timezone.utc).replace(tzinfo=None) if req.consent_given else None,
        data_categories=req.data_categories,
        tenant_id=get_tenant_id(request),
    )
    db.add(subj)
    await db.flush()
    return _ser_subject(subj)


@router.get("/subjects/{subject_id}", dependencies=[Depends(require_permission("privacy:read"))])
async def get_subject(subject_id: UUID, db: AsyncSession = Depends(get_db)):
    subj = await db.get(PrivacySubject, subject_id)
    if not subj:
        raise HTTPException(404, "Privacy subject not found")
    return _ser_subject(subj)


@router.post("/subjects/{subject_id}/erasure", dependencies=[Depends(require_permission("privacy:manage"))])
async def request_erasure(subject_id: UUID, db: AsyncSession = Depends(get_db)):
    """GDPR Article 17 - Right to Erasure (Right to be Forgotten)"""
    subj = await db.get(PrivacySubject, subject_id)
    if not subj:
        raise HTTPException(404, "Privacy subject not found")
    from datetime import datetime, timezone
    subj.erasure_requested = True
    subj.erasure_requested_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.flush()
    return {"status": "erasure_requested", "subject_id": str(subject_id)}


# --- Consent ---

@router.get("/consent", dependencies=[Depends(require_permission("privacy:read"))])
async def list_consent_records(subject_id: Optional[str] = None, skip: int = Query(0), limit: int = Query(50), db: AsyncSession = Depends(get_db)):
    q = select(PrivacyConsentRecord)
    if subject_id:
        q = q.where(PrivacyConsentRecord.subject_id == subject_id)
    result = await db.execute(q.offset(skip).limit(limit).order_by(PrivacyConsentRecord.granted_at.desc()))
    items = result.scalars().all()
    return {"items": [_ser_consent(c) for c in items], "total": len(items)}


@router.post("/consent", status_code=201, dependencies=[Depends(require_permission("privacy:manage"))])
async def record_consent(req: ConsentCreate, request: Request, db: AsyncSession = Depends(get_db)):
    record = PrivacyConsentRecord(
        subject_id=req.subject_id, purpose=req.purpose,
        legal_basis=req.legal_basis, granted=req.granted,
        tenant_id=get_tenant_id(request),
    )
    db.add(record)
    await db.flush()
    return _ser_consent(record)


@router.post("/consent/{consent_id}/revoke", dependencies=[Depends(require_permission("privacy:manage"))])
async def revoke_consent(consent_id: UUID, db: AsyncSession = Depends(get_db)):
    record = await db.get(PrivacyConsentRecord, consent_id)
    if not record:
        raise HTTPException(404, "Consent record not found")
    from datetime import datetime, timezone
    record.revoked_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.flush()
    return {"status": "revoked", "consent_id": str(consent_id)}


# --- Data Exports ---

@router.get("/exports", dependencies=[Depends(require_permission("privacy:read"))])
async def list_exports(skip: int = Query(0), limit: int = Query(50, le=200), db: AsyncSession = Depends(get_db)):
    total = await db.scalar(select(func.count()).select_from(PrivacyDataExport))
    result = await db.execute(select(PrivacyDataExport).offset(skip).limit(limit).order_by(PrivacyDataExport.requested_at.desc()))
    items = result.scalars().all()
    return {"items": [_ser_export(e) for e in items], "total": total or 0, "skip": skip, "limit": limit}


@router.post("/exports", status_code=201, dependencies=[Depends(require_permission("privacy:manage"))])
async def request_data_export(req: DataExportRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """GDPR Article 20 - Right to Data Portability"""
    export = PrivacyDataExport(
        subject_id=req.subject_id, requested_by=req.requested_by,
        export_format=req.export_format,
        tenant_id=get_tenant_id(request),
    )
    db.add(export)
    await db.flush()
    return _ser_export(export)


# --- Serializers ---

def _ser_subject(s: PrivacySubject) -> dict:
    return {
        "id": str(s.id), "subject_type": s.subject_type,
        "subject_identifier": s.subject_identifier,
        "consent_given": s.consent_given,
        "consent_date": str(s.consent_date) if s.consent_date else None,
        "data_categories": s.data_categories,
        "erasure_requested": s.erasure_requested,
        "created_at": str(s.created_at) if s.created_at else None,
    }


def _ser_consent(c: PrivacyConsentRecord) -> dict:
    return {
        "id": str(c.id), "subject_id": str(c.subject_id),
        "purpose": c.purpose, "legal_basis": c.legal_basis,
        "granted": c.granted,
        "granted_at": str(c.granted_at) if c.granted_at else None,
        "revoked_at": str(c.revoked_at) if c.revoked_at else None,
    }


def _ser_export(e: PrivacyDataExport) -> dict:
    return {
        "id": str(e.id), "subject_id": str(e.subject_id),
        "requested_by": e.requested_by, "status": e.status,
        "export_format": e.export_format,
        "requested_at": str(e.requested_at) if e.requested_at else None,
        "completed_at": str(e.completed_at) if e.completed_at else None,
    }
