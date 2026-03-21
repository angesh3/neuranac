"""AI Data Flow policies and shadow AI detection router"""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database.session import get_db
from app.models.network import AIDataFlowPolicy, AIShadowDetection, AIService
from app.middleware.auth import require_permission
from app.middleware.tenant_helper import get_tenant_id

router = APIRouter()


class DataFlowPolicyCreate(BaseModel):
    name: str
    priority: int = 1
    source_conditions: dict = {}
    dest_conditions: dict = {}
    data_classification: Optional[str] = None
    action: str = "deny"
    max_volume_mb: Optional[int] = None


@router.get("/policies", dependencies=[Depends(require_permission("ai:read"))])
async def list_data_flow_policies(skip: int = Query(0), limit: int = Query(50), db: AsyncSession = Depends(get_db)):
    total = await db.scalar(select(func.count()).select_from(AIDataFlowPolicy))
    result = await db.execute(select(AIDataFlowPolicy).offset(skip).limit(limit).order_by(AIDataFlowPolicy.priority))
    items = result.scalars().all()
    return {"items": [_ser_policy(p) for p in items], "total": total or 0}


@router.post("/policies", status_code=201, dependencies=[Depends(require_permission("ai:manage"))])
async def create_data_flow_policy(req: DataFlowPolicyCreate, request: Request, db: AsyncSession = Depends(get_db)):
    policy = AIDataFlowPolicy(
        name=req.name, priority=req.priority, source_conditions=req.source_conditions,
        dest_conditions=req.dest_conditions, data_classification=req.data_classification,
        action=req.action, max_volume_mb=req.max_volume_mb,
        tenant_id=get_tenant_id(request),
    )
    db.add(policy)
    await db.flush()
    return _ser_policy(policy)


@router.get("/services", dependencies=[Depends(require_permission("ai:read"))])
async def list_ai_services(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AIService).order_by(AIService.name))
    items = result.scalars().all()
    return {"items": [_ser_svc(s) for s in items], "total": len(items)}


@router.get("/detections", dependencies=[Depends(require_permission("ai:read"))])
async def list_shadow_detections(skip: int = Query(0), limit: int = Query(50), db: AsyncSession = Depends(get_db)):
    total = await db.scalar(select(func.count()).select_from(AIShadowDetection))
    result = await db.execute(select(AIShadowDetection).offset(skip).limit(limit).order_by(AIShadowDetection.detected_at.desc()))
    items = result.scalars().all()
    return {"items": [_ser_det(d) for d in items], "total": total or 0}


def _ser_policy(p: AIDataFlowPolicy) -> dict:
    return {"id": str(p.id), "name": p.name, "priority": p.priority,
            "source_conditions": p.source_conditions, "dest_conditions": p.dest_conditions,
            "data_classification": p.data_classification, "action": p.action,
            "max_volume_mb": p.max_volume_mb, "status": p.status}


def _ser_svc(s: AIService) -> dict:
    return {"id": str(s.id), "name": s.name, "category": s.category,
            "dns_patterns": s.dns_patterns, "risk_level": s.risk_level,
            "is_approved": s.is_approved, "is_builtin": s.is_builtin}


def _ser_det(d: AIShadowDetection) -> dict:
    return {"id": str(d.id), "endpoint_mac": d.endpoint_mac, "user_id": d.user_id,
            "detection_type": d.detection_type, "bytes_uploaded": d.bytes_uploaded,
            "bytes_downloaded": d.bytes_downloaded, "action_taken": d.action_taken,
            "detected_at": str(d.detected_at) if d.detected_at else None}
