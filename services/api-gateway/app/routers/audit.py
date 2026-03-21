"""Audit log router - tamper-proof chain, search, export"""
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel

from app.database.session import get_db
from app.models.admin import AuditLog
from app.services.audit_chain import AuditChainService

router = APIRouter()
_chain = AuditChainService()


@router.get("/")
async def list_audit_logs(
    skip: int = Query(0), limit: int = Query(100),
    actor: Optional[str] = None, action: Optional[str] = None,
    entity_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(AuditLog)
    cq = select(func.count()).select_from(AuditLog)
    if actor:
        q = q.where(AuditLog.actor.ilike(f"%{actor}%"))
        cq = cq.where(AuditLog.actor.ilike(f"%{actor}%"))
    if action:
        q = q.where(AuditLog.action == action)
        cq = cq.where(AuditLog.action == action)
    if entity_type:
        q = q.where(AuditLog.entity_type == entity_type)
        cq = cq.where(AuditLog.entity_type == entity_type)
    total = await db.scalar(cq)
    result = await db.execute(q.offset(skip).limit(limit).order_by(AuditLog.timestamp.desc()))
    items = result.scalars().all()
    return {"items": [_ser(a) for a in items], "total": total or 0, "skip": skip, "limit": limit}


class AuditEntryCreate(BaseModel):
    actor: str
    action: str
    entity_type: Optional[str] = None
    entity_id: Optional[str] = None
    before_data: Optional[dict] = None
    after_data: Optional[dict] = None
    source_ip: Optional[str] = None


@router.post("/")
async def create_audit_entry(body: AuditEntryCreate, db: AsyncSession = Depends(get_db)):
    """Create a new audit log entry with hash-chain integrity."""
    import uuid
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc).replace(tzinfo=None)
    entry_data = {**body.model_dump(), "timestamp": now}
    entry_hash, prev_hash = await _chain.compute_chain_hashes(db, entry_data)

    log = AuditLog(
        id=uuid.uuid4(),
        actor=body.actor,
        action=body.action,
        entity_type=body.entity_type,
        entity_id=body.entity_id,
        before_data=body.before_data,
        after_data=body.after_data,
        source_ip=body.source_ip,
        timestamp=now,
        prev_hash=prev_hash,
        entry_hash=entry_hash,
    )
    db.add(log)
    await db.commit()
    return _ser(log)


@router.get("/verify-chain")
async def verify_audit_chain(
    limit: int = Query(10000, le=50000),
    db: AsyncSession = Depends(get_db),
):
    """Verify the tamper-proof audit log chain integrity."""
    return await _chain.verify_chain(db, limit=limit)


@router.post("/backfill-hashes")
async def backfill_audit_hashes(
    batch_size: int = Query(500, le=5000),
    db: AsyncSession = Depends(get_db),
):
    """Backfill entry_hash and prev_hash for rows that are missing them."""
    updated = await _chain.backfill_hashes(db, batch_size=batch_size)
    return {"status": "ok", "rows_updated": updated}


@router.get("/reports/summary")
async def audit_summary_report(days: int = Query(7), db: AsyncSession = Depends(get_db)):
    """Generate audit summary report for the last N days"""
    from sqlalchemy import text
    result = await db.execute(
        text("""
            SELECT action, COUNT(*) as count
            FROM audit_logs
            WHERE timestamp > NOW() - INTERVAL '1 day' * :days
            GROUP BY action ORDER BY count DESC
        """),
        {"days": days},
    )
    rows = result.fetchall()
    actions = [{"action": r[0], "count": r[1]} for r in rows]

    total_result = await db.execute(
        text("SELECT COUNT(*) FROM audit_logs WHERE timestamp > NOW() - INTERVAL '1 day' * :days"),
        {"days": days},
    )
    total = total_result.scalar() or 0

    return {
        "period_days": days,
        "total_events": total,
        "actions_breakdown": actions,
    }


@router.get("/reports/auth")
async def auth_report(days: int = Query(7), db: AsyncSession = Depends(get_db)):
    """Authentication attempts report"""
    from sqlalchemy import text
    result = await db.execute(
        text("""
            SELECT
                DATE(timestamp) as day,
                COUNT(*) FILTER (WHERE action = 'auth_success') as successes,
                COUNT(*) FILTER (WHERE action = 'auth_failure') as failures
            FROM audit_logs
            WHERE timestamp > NOW() - INTERVAL '1 day' * :days
              AND action IN ('auth_success', 'auth_failure')
            GROUP BY DATE(timestamp) ORDER BY day
        """),
        {"days": days},
    )
    rows = result.fetchall()
    daily = [{"date": str(r[0]), "successes": r[1], "failures": r[2]} for r in rows]
    return {"period_days": days, "daily_auth": daily}


@router.get("/{log_id}")
async def get_audit_log(log_id: UUID, db: AsyncSession = Depends(get_db)):
    log = await db.get(AuditLog, log_id)
    if not log:
        from fastapi import HTTPException
        raise HTTPException(404, "Audit log not found")
    return _ser(log)


def _ser(a: AuditLog) -> dict:
    return {
        "id": str(a.id), "actor": a.actor, "action": a.action,
        "entity_type": a.entity_type, "entity_id": a.entity_id,
        "before_data": a.before_data, "after_data": a.after_data,
        "source_ip": a.source_ip,
        "timestamp": str(a.timestamp) if a.timestamp else None,
        "entry_hash": a.entry_hash,
    }
