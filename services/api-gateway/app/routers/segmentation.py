"""Segmentation router - SGTs, adaptive policies, VLANs, ACLs"""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database.session import get_db
from app.models.network import SecurityGroup
from app.middleware.auth import require_permission
from app.middleware.tenant_helper import get_tenant_id

router = APIRouter()


class SGTCreate(BaseModel):
    name: str
    tag_value: int
    description: Optional[str] = None
    is_ai_sgt: bool = False


@router.get("/sgts", dependencies=[Depends(require_permission("segmentation:read"))])
async def list_sgts(skip: int = Query(0), limit: int = Query(50), db: AsyncSession = Depends(get_db)):
    total = await db.scalar(select(func.count()).select_from(SecurityGroup))
    result = await db.execute(select(SecurityGroup).offset(skip).limit(limit).order_by(SecurityGroup.tag_value))
    items = result.scalars().all()
    return {"items": [_ser(s) for s in items], "total": total or 0}


@router.post("/sgts", status_code=201, dependencies=[Depends(require_permission("segmentation:write"))])
async def create_sgt(req: SGTCreate, request: Request, db: AsyncSession = Depends(get_db)):
    sgt = SecurityGroup(name=req.name, tag_value=req.tag_value, description=req.description,
                        is_ai_sgt=req.is_ai_sgt, tenant_id=get_tenant_id(request))
    db.add(sgt)
    await db.flush()
    return _ser(sgt)


@router.get("/sgts/{sgt_id}", dependencies=[Depends(require_permission("segmentation:read"))])
async def get_sgt(sgt_id: UUID, db: AsyncSession = Depends(get_db)):
    sgt = await db.get(SecurityGroup, sgt_id)
    if not sgt:
        raise HTTPException(404, "SGT not found")
    return _ser(sgt)


@router.delete("/sgts/{sgt_id}", status_code=204, dependencies=[Depends(require_permission("segmentation:write"))])
async def delete_sgt(sgt_id: UUID, db: AsyncSession = Depends(get_db)):
    sgt = await db.get(SecurityGroup, sgt_id)
    if not sgt:
        raise HTTPException(404, "SGT not found")
    await db.delete(sgt)


@router.put("/sgts/{sgt_id}", dependencies=[Depends(require_permission("segmentation:write"))])
async def update_sgt(sgt_id: UUID, req: SGTCreate, db: AsyncSession = Depends(get_db)):
    sgt = await db.get(SecurityGroup, sgt_id)
    if not sgt:
        raise HTTPException(404, "SGT not found")
    sgt.name = req.name
    sgt.tag_value = req.tag_value
    sgt.description = req.description
    sgt.is_ai_sgt = req.is_ai_sgt
    await db.flush()
    return _ser(sgt)


@router.get("/matrix", dependencies=[Depends(require_permission("segmentation:read"))])
async def get_policy_matrix(db: AsyncSession = Depends(get_db)):
    """Get the SGT-to-SGT adaptive policy matrix with AI enforcement info"""
    result = await db.execute(select(SecurityGroup).order_by(SecurityGroup.tag_value))
    sgts = result.scalars().all()
    sgt_list = [_ser(s) for s in sgts]

    # Build matrix: each source SGT → destination SGT with default policy
    matrix = []
    for src in sgts:
        for dst in sgts:
            policy = "permit" if src.tag_value == dst.tag_value else "deny"
            if src.is_ai_sgt or dst.is_ai_sgt:
                policy = "ai-inspect"
            matrix.append({
                "source_sgt": src.tag_value,
                "destination_sgt": dst.tag_value,
                "policy": policy,
            })

    return {"matrix": matrix, "sgts": sgt_list, "total_sgts": len(sgt_list)}


def _ser(s: SecurityGroup) -> dict:
    return {"id": str(s.id), "name": s.name, "tag_value": s.tag_value,
            "description": s.description, "is_ai_sgt": s.is_ai_sgt,
            "created_at": str(s.created_at) if s.created_at else None}
