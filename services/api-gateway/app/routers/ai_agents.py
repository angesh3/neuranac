"""AI Agents CRUD router - manage AI agent identities and delegations"""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database.session import get_db
from app.models.network import AIAgent
from app.middleware.auth import require_permission
from app.middleware.tenant_helper import get_tenant_id
from app.services.delegation_chain import DelegationChainValidator

router = APIRouter()


class AIAgentCreate(BaseModel):
    agent_name: str
    agent_type: str
    delegated_by_user_id: Optional[str] = None
    delegation_scope: List[str] = []
    model_type: Optional[str] = None
    runtime: Optional[str] = None
    auth_method: Optional[str] = None
    max_bandwidth_mbps: Optional[int] = None
    data_classification_allowed: List[str] = []
    ttl_hours: int = 24


class AIAgentUpdate(BaseModel):
    agent_name: Optional[str] = None
    delegation_scope: Optional[List[str]] = None
    status: Optional[str] = None
    max_bandwidth_mbps: Optional[int] = None
    data_classification_allowed: Optional[List[str]] = None
    ttl_hours: Optional[int] = None


@router.get("/", dependencies=[Depends(require_permission("ai:read"))])
async def list_ai_agents(skip: int = Query(0), limit: int = Query(50), status: Optional[str] = None, db: AsyncSession = Depends(get_db)):
    q = select(AIAgent)
    cq = select(func.count()).select_from(AIAgent)
    if status:
        q = q.where(AIAgent.status == status)
        cq = cq.where(AIAgent.status == status)
    total = await db.scalar(cq)
    result = await db.execute(q.offset(skip).limit(limit).order_by(AIAgent.created_at.desc()))
    items = result.scalars().all()
    return {"items": [_serialize(a) for a in items], "total": total or 0, "skip": skip, "limit": limit}


@router.get("/{agent_id}", dependencies=[Depends(require_permission("ai:read"))])
async def get_ai_agent(agent_id: UUID, db: AsyncSession = Depends(get_db)):
    agent = await db.get(AIAgent, agent_id)
    if not agent:
        raise HTTPException(404, "AI Agent not found")
    return _serialize(agent)


@router.post("/", status_code=201, dependencies=[Depends(require_permission("ai:manage"))])
async def create_ai_agent(req: AIAgentCreate, request: Request, db: AsyncSession = Depends(get_db)):
    agent = AIAgent(
        agent_name=req.agent_name, agent_type=req.agent_type,
        delegation_scope=req.delegation_scope, model_type=req.model_type,
        runtime=req.runtime, auth_method=req.auth_method,
        max_bandwidth_mbps=req.max_bandwidth_mbps,
        data_classification_allowed=req.data_classification_allowed,
        ttl_hours=req.ttl_hours,
        tenant_id=get_tenant_id(request),
    )
    db.add(agent)
    await db.flush()
    return _serialize(agent)


@router.put("/{agent_id}", dependencies=[Depends(require_permission("ai:manage"))])
async def update_ai_agent(agent_id: UUID, req: AIAgentUpdate, db: AsyncSession = Depends(get_db)):
    agent = await db.get(AIAgent, agent_id)
    if not agent:
        raise HTTPException(404, "AI Agent not found")
    for k, v in req.model_dump(exclude_unset=True).items():
        setattr(agent, k, v)
    await db.flush()
    return _serialize(agent)


@router.delete("/{agent_id}", status_code=204, dependencies=[Depends(require_permission("ai:manage"))])
async def delete_ai_agent(agent_id: UUID, db: AsyncSession = Depends(get_db)):
    agent = await db.get(AIAgent, agent_id)
    if not agent:
        raise HTTPException(404, "AI Agent not found")
    await db.delete(agent)


@router.post("/{agent_id}/revoke", dependencies=[Depends(require_permission("ai:manage"))])
async def revoke_ai_agent(agent_id: UUID, db: AsyncSession = Depends(get_db)):
    agent = await db.get(AIAgent, agent_id)
    if not agent:
        raise HTTPException(404, "AI Agent not found")
    agent.status = "revoked"
    await db.flush()
    return {"status": "revoked", "agent_id": str(agent_id)}


@router.get("/{agent_id}/delegation-chain", dependencies=[Depends(require_permission("ai:read"))])
async def validate_delegation_chain(agent_id: UUID, db: AsyncSession = Depends(get_db)):
    """Validate the full delegation chain for an AI agent."""
    validator = DelegationChainValidator(db)
    result = await validator.validate(agent_id)
    if not result["valid"]:
        raise HTTPException(403, detail=result)
    return result


@router.post("/{agent_id}/check-scope", dependencies=[Depends(require_permission("ai:read"))])
async def check_agent_scope(agent_id: UUID, action: str = Query(..., description="Scope to check, e.g. policy:read"), db: AsyncSession = Depends(get_db)):
    """Check whether an AI agent is authorized for a specific action via delegation chain."""
    validator = DelegationChainValidator(db)
    result = await validator.validate_scope_request(agent_id, action)
    if not result["allowed"]:
        raise HTTPException(403, detail=result)
    return result


def _serialize(a: AIAgent) -> dict:
    return {
        "id": str(a.id), "agent_name": a.agent_name, "agent_type": a.agent_type,
        "delegation_scope": a.delegation_scope, "model_type": a.model_type,
        "runtime": a.runtime, "auth_method": a.auth_method, "status": a.status,
        "max_bandwidth_mbps": a.max_bandwidth_mbps,
        "data_classification_allowed": a.data_classification_allowed,
        "ttl_hours": a.ttl_hours,
        "created_at": str(a.created_at) if a.created_at else None,
    }
