"""Sessions router - live and historical RADIUS sessions"""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database.session import get_db
from app.models.network import Session

router = APIRouter()


@router.get("/")
async def list_sessions(
    skip: int = Query(0), limit: int = Query(50),
    active: Optional[bool] = None, mac: Optional[str] = None,
    username: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(Session)
    cq = select(func.count()).select_from(Session)
    if active is not None:
        q = q.where(Session.is_active == active)
        cq = cq.where(Session.is_active == active)
    if mac:
        q = q.where(Session.endpoint_mac == mac)
        cq = cq.where(Session.endpoint_mac == mac)
    if username:
        q = q.where(Session.username.ilike(f"%{username}%"))
        cq = cq.where(Session.username.ilike(f"%{username}%"))
    total = await db.scalar(cq)
    result = await db.execute(q.offset(skip).limit(limit).order_by(Session.started_at.desc()))
    items = result.scalars().all()
    return {"items": [_serialize(s) for s in items], "total": total or 0, "skip": skip, "limit": limit}


@router.get("/active/count")
async def active_session_count(db: AsyncSession = Depends(get_db)):
    count = await db.scalar(select(func.count()).select_from(Session).where(Session.is_active == True))
    return {"active_sessions": count or 0}


@router.get("/{session_id}")
async def get_session(session_id: UUID, db: AsyncSession = Depends(get_db)):
    sess = await db.get(Session, session_id)
    if not sess:
        raise HTTPException(404, "Session not found")
    return _serialize(sess)


@router.post("/{session_id}/disconnect")
async def disconnect_session(session_id: UUID, db: AsyncSession = Depends(get_db)):
    sess = await db.get(Session, session_id)
    if not sess:
        raise HTTPException(404, "Session not found")
    sess.is_active = False
    from datetime import datetime, timezone
    sess.ended_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.flush()
    return {"status": "disconnected", "session_id": str(session_id)}


@router.post("/{session_id}/reauthenticate")
async def reauthenticate_session(session_id: UUID, db: AsyncSession = Depends(get_db)):
    sess = await db.get(Session, session_id)
    if not sess:
        raise HTTPException(404, "Session not found")
    return {"status": "coa_sent", "session_id": str(session_id), "action": "reauthenticate"}


def _serialize(s: Session) -> dict:
    return {
        "id": str(s.id), "session_id_radius": s.session_id_radius,
        "endpoint_mac": s.endpoint_mac, "username": s.username,
        "nas_ip": s.nas_ip, "eap_type": s.eap_type,
        "auth_result": s.auth_result, "vlan_id": s.vlan_id, "sgt": s.sgt,
        "risk_score": s.risk_score, "ai_agent_id": str(s.ai_agent_id) if s.ai_agent_id else None,
        "accounting": s.accounting, "is_active": s.is_active,
        "started_at": str(s.started_at) if s.started_at else None,
        "ended_at": str(s.ended_at) if s.ended_at else None,
    }
