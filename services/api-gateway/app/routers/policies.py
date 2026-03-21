"""Policy sets, rules, and authorization profiles CRUD router"""
import json
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
import structlog

from app.database.session import get_db
from app.models.network import PolicySet, PolicyRule, AuthorizationProfile
from app.middleware.auth import require_permission
from app.middleware.tenant_helper import get_tenant_id

logger = structlog.get_logger()
router = APIRouter()


async def _publish_policy_change(entity_type: str, entity_id: str, operation: str):
    """Publish incremental policy change to NATS so RADIUS/sync consumers reload."""
    try:
        from app.services.nats_client import get_nats_js
        js = get_nats_js()
        if js:
            payload = json.dumps({
                "entity_type": entity_type,
                "entity_id": entity_id,
                "operation": operation,
            }).encode()
            await js.publish("neuranac.policy.changed", payload)
    except Exception as exc:
        logger.debug("NATS policy publish failed (non-critical)", error=str(exc))


class PolicySetCreate(BaseModel):
    name: str
    description: Optional[str] = None
    priority: int = 1


class PolicyRuleCreate(BaseModel):
    name: str
    priority: int = 1
    conditions: List[dict] = []
    auth_profile_id: Optional[str] = None
    action: str = "permit"


class AuthProfileCreate(BaseModel):
    name: str
    vlan_id: Optional[str] = None
    vlan_name: Optional[str] = None
    sgt_value: Optional[int] = None
    ipsk: Optional[str] = None
    coa_action: Optional[str] = None
    group_policy: Optional[str] = None
    voice_domain: bool = False
    redirect_url: Optional[str] = None
    session_timeout: Optional[int] = None
    bandwidth_limit_mbps: Optional[int] = None
    destination_whitelist: List[str] = []
    vendor_attributes: Optional[dict] = None


@router.get("/", dependencies=[Depends(require_permission("policy:read"))])
async def list_policy_sets(skip: int = Query(0), limit: int = Query(50), db: AsyncSession = Depends(get_db)):
    total = await db.scalar(select(func.count()).select_from(PolicySet))
    result = await db.execute(select(PolicySet).offset(skip).limit(limit).order_by(PolicySet.priority))
    items = result.scalars().all()
    return {"items": [_ser_ps(p) for p in items], "total": total or 0, "skip": skip, "limit": limit}


@router.post("/", status_code=201, dependencies=[Depends(require_permission("policy:write"))])
async def create_policy_set(req: PolicySetCreate, request: Request, db: AsyncSession = Depends(get_db)):
    ps = PolicySet(name=req.name, description=req.description, priority=req.priority,
                   tenant_id=get_tenant_id(request))
    db.add(ps)
    await db.flush()
    await _publish_policy_change("policy_set", str(ps.id), "create")
    return _ser_ps(ps)


@router.get("/{policy_set_id}", dependencies=[Depends(require_permission("policy:read"))])
async def get_policy_set(policy_set_id: UUID, db: AsyncSession = Depends(get_db)):
    ps = await db.get(PolicySet, policy_set_id)
    if not ps:
        raise HTTPException(404, "Policy set not found")
    return _ser_ps(ps)


@router.put("/{policy_set_id}", dependencies=[Depends(require_permission("policy:write"))])
async def update_policy_set(policy_set_id: UUID, req: PolicySetCreate, db: AsyncSession = Depends(get_db)):
    ps = await db.get(PolicySet, policy_set_id)
    if not ps:
        raise HTTPException(404, "Policy set not found")
    ps.name = req.name
    if req.description is not None:
        ps.description = req.description
    ps.priority = req.priority
    await db.flush()
    await _publish_policy_change("policy_set", str(policy_set_id), "update")
    return _ser_ps(ps)


@router.delete("/{policy_set_id}", status_code=204, dependencies=[Depends(require_permission("policy:write"))])
async def delete_policy_set(policy_set_id: UUID, db: AsyncSession = Depends(get_db)):
    ps = await db.get(PolicySet, policy_set_id)
    if not ps:
        raise HTTPException(404, "Policy set not found")
    await db.delete(ps)
    await _publish_policy_change("policy_set", str(policy_set_id), "delete")


@router.get("/{policy_set_id}/rules", dependencies=[Depends(require_permission("policy:read"))])
async def list_rules(policy_set_id: UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(PolicyRule).where(PolicyRule.policy_set_id == policy_set_id).order_by(PolicyRule.priority)
    )
    rules = result.scalars().all()
    return {"items": [_ser_rule(r) for r in rules], "total": len(rules)}


@router.post("/{policy_set_id}/rules", status_code=201, dependencies=[Depends(require_permission("policy:write"))])
async def create_rule(policy_set_id: UUID, req: PolicyRuleCreate, db: AsyncSession = Depends(get_db)):
    rule = PolicyRule(
        policy_set_id=policy_set_id, name=req.name, priority=req.priority,
        conditions=req.conditions, auth_profile_id=req.auth_profile_id, action=req.action,
    )
    db.add(rule)
    await db.flush()
    await _publish_policy_change("policy_rule", str(rule.id), "create")
    return _ser_rule(rule)


@router.put("/{policy_set_id}/rules/{rule_id}", dependencies=[Depends(require_permission("policy:write"))])
async def update_rule(policy_set_id: UUID, rule_id: UUID, req: PolicyRuleCreate, db: AsyncSession = Depends(get_db)):
    rule = await db.get(PolicyRule, rule_id)
    if not rule or str(rule.policy_set_id) != str(policy_set_id):
        raise HTTPException(404, "Rule not found")
    rule.name = req.name
    rule.priority = req.priority
    rule.conditions = req.conditions
    rule.auth_profile_id = req.auth_profile_id
    rule.action = req.action
    await db.flush()
    await _publish_policy_change("policy_rule", str(rule_id), "update")
    return _ser_rule(rule)


@router.delete("/{policy_set_id}/rules/{rule_id}", status_code=204, dependencies=[Depends(require_permission("policy:write"))])
async def delete_rule(policy_set_id: UUID, rule_id: UUID, db: AsyncSession = Depends(get_db)):
    rule = await db.get(PolicyRule, rule_id)
    if not rule or str(rule.policy_set_id) != str(policy_set_id):
        raise HTTPException(404, "Rule not found")
    await db.delete(rule)
    await _publish_policy_change("policy_rule", str(rule_id), "delete")


@router.get("/auth-profiles/", dependencies=[Depends(require_permission("policy:read"))])
async def list_auth_profiles(skip: int = Query(0), limit: int = Query(50), db: AsyncSession = Depends(get_db)):
    total = await db.scalar(select(func.count()).select_from(AuthorizationProfile))
    result = await db.execute(select(AuthorizationProfile).offset(skip).limit(limit))
    items = result.scalars().all()
    return {"items": [_ser_ap(a) for a in items], "total": total or 0}


@router.post("/auth-profiles/", status_code=201, dependencies=[Depends(require_permission("policy:write"))])
async def create_auth_profile(req: AuthProfileCreate, request: Request, db: AsyncSession = Depends(get_db)):
    ap = AuthorizationProfile(
        name=req.name, vlan_id=req.vlan_id, vlan_name=req.vlan_name, sgt_value=req.sgt_value,
        ipsk=req.ipsk, coa_action=req.coa_action, group_policy=req.group_policy,
        voice_domain=req.voice_domain, redirect_url=req.redirect_url,
        session_timeout=req.session_timeout, bandwidth_limit_mbps=req.bandwidth_limit_mbps,
        destination_whitelist=req.destination_whitelist, vendor_attributes=req.vendor_attributes or {},
        tenant_id=get_tenant_id(request),
    )
    db.add(ap)
    await db.flush()
    await _publish_policy_change("auth_profile", str(ap.id), "create")
    return _ser_ap(ap)


def _ser_ps(p: PolicySet) -> dict:
    return {"id": str(p.id), "name": p.name, "description": p.description, "priority": p.priority,
            "status": p.status, "created_at": str(p.created_at) if p.created_at else None}


def _ser_rule(r: PolicyRule) -> dict:
    return {"id": str(r.id), "policy_set_id": str(r.policy_set_id), "name": r.name, "priority": r.priority,
            "conditions": r.conditions, "auth_profile_id": str(r.auth_profile_id) if r.auth_profile_id else None,
            "action": r.action, "status": r.status}


def _ser_ap(a: AuthorizationProfile) -> dict:
    return {"id": str(a.id), "name": a.name, "vlan_id": a.vlan_id, "vlan_name": a.vlan_name,
            "sgt_value": a.sgt_value, "ipsk": a.ipsk, "coa_action": a.coa_action,
            "voice_domain": a.voice_domain, "redirect_url": a.redirect_url,
            "session_timeout": a.session_timeout, "bandwidth_limit_mbps": a.bandwidth_limit_mbps}
