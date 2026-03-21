"""Posture & Compliance router"""
import json
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel
from typing import Optional, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database.session import get_db
from app.models.network import PosturePolicy
from app.middleware.tenant_helper import get_tenant_id

router = APIRouter()


class PosturePolicyCreate(BaseModel):
    name: str
    conditions: List[dict] = []
    grace_period_hours: int = 0


@router.get("/policies")
async def list_posture_policies(skip: int = Query(0), limit: int = Query(50, le=200), db: AsyncSession = Depends(get_db)):
    total = await db.scalar(select(func.count()).select_from(PosturePolicy))
    result = await db.execute(select(PosturePolicy).offset(skip).limit(limit).order_by(PosturePolicy.created_at.desc()))
    items = result.scalars().all()
    return {"items": [_ser(p) for p in items], "total": total or 0, "skip": skip, "limit": limit}


@router.post("/policies", status_code=201)
async def create_posture_policy(req: PosturePolicyCreate, request: Request, db: AsyncSession = Depends(get_db)):
    policy = PosturePolicy(name=req.name, conditions=req.conditions,
                           grace_period_hours=req.grace_period_hours,
                           tenant_id=get_tenant_id(request))
    db.add(policy)
    await db.flush()
    return _ser(policy)


@router.get("/policies/{policy_id}")
async def get_posture_policy(policy_id: UUID, db: AsyncSession = Depends(get_db)):
    policy = await db.get(PosturePolicy, policy_id)
    if not policy:
        raise HTTPException(404, "Posture policy not found")
    return _ser(policy)


@router.delete("/policies/{policy_id}", status_code=204)
async def delete_posture_policy(policy_id: UUID, db: AsyncSession = Depends(get_db)):
    policy = await db.get(PosturePolicy, policy_id)
    if not policy:
        raise HTTPException(404, "Posture policy not found")
    await db.delete(policy)


class PostureAssessmentRequest(BaseModel):
    endpoint_mac: str
    checks: List[dict] = []  # e.g. [{"type":"antivirus","required":true},{"type":"os_patch","min_version":"10.0"}]


@router.post("/assess")
async def assess_endpoint_posture(req: PostureAssessmentRequest, request: Request, db: AsyncSession = Depends(get_db)):
    """Run posture assessment against all active policies for an endpoint"""
    result = await db.execute(select(PosturePolicy).where(PosturePolicy.status == "active"))
    policies = result.scalars().all()

    # Look up endpoint's reported posture data
    from sqlalchemy import text
    ep_result = await db.execute(
        text("SELECT attributes FROM endpoints WHERE mac_address = :mac LIMIT 1"),
        {"mac": req.endpoint_mac},
    )
    ep_row = ep_result.fetchone()
    ep_attrs = ep_row[0] if ep_row and ep_row[0] else {}

    # Merge agent-reported checks from request with DB attributes
    agent_checks = {c.get("type"): c for c in req.checks}

    findings = []
    compliant = True
    for policy in policies:
        for cond in (policy.conditions or []):
            check_type = cond.get("type", "")
            required = cond.get("required", True)

            # Evaluate posture condition against real data
            passed = _evaluate_posture_check(check_type, cond, ep_attrs, agent_checks)
            if not passed and required:
                compliant = False
            findings.append({
                "policy_id": str(policy.id),
                "policy_name": policy.name,
                "check_type": check_type,
                "passed": passed,
                "required": required,
                "details": cond,
            })

    status = "compliant" if compliant else "noncompliant"

    # Store posture result
    await db.execute(
        text("""INSERT INTO posture_results (tenant_id, endpoint_mac, status, details)
                VALUES (:tid, :mac, :status, :details)"""),
        {"tid": get_tenant_id(request), "mac": req.endpoint_mac,
         "status": status, "details": json.dumps({"findings": findings})},
    )
    await db.commit()

    return {
        "endpoint_mac": req.endpoint_mac,
        "status": status,
        "findings": findings,
        "policies_evaluated": len(policies),
    }


@router.get("/results")
async def list_posture_results(skip: int = Query(0), limit: int = Query(50), db: AsyncSession = Depends(get_db)):
    from sqlalchemy import text
    result = await db.execute(
        text("SELECT id, tenant_id, endpoint_mac, status, assessed_at FROM posture_results ORDER BY assessed_at DESC LIMIT :limit OFFSET :skip"),
        {"limit": limit, "skip": skip},
    )
    rows = result.fetchall()
    items = [{"id": str(r[0]), "tenant_id": str(r[1]), "endpoint_mac": r[2], "status": r[3], "assessed_at": str(r[4])} for r in rows]
    return {"items": items, "total": len(items), "skip": skip, "limit": limit}


def _evaluate_posture_check(check_type: str, condition: dict, ep_attrs: dict, agent_checks: dict) -> bool:
    """Evaluate a single posture condition against endpoint data.
    Checks agent-reported data first, then endpoint DB attributes."""
    # Agent-reported check takes priority
    if check_type in agent_checks:
        agent = agent_checks[check_type]
        return agent.get("status", "unknown") in ("ok", "pass", "compliant", "true", True)

    posture = ep_attrs.get("posture", {})
    if isinstance(posture, str):
        try:
            posture = json.loads(posture)
        except (json.JSONDecodeError, TypeError):
            posture = {}

    if check_type == "antivirus":
        return posture.get("antivirus_installed", False) and posture.get("antivirus_running", False)
    elif check_type == "firewall":
        return posture.get("firewall_enabled", False)
    elif check_type == "disk_encryption":
        return posture.get("disk_encrypted", False)
    elif check_type == "os_patch":
        min_version = condition.get("min_version", "0")
        current = posture.get("os_patch_level", "0")
        try:
            return float(current) >= float(min_version)
        except (ValueError, TypeError):
            return False
    elif check_type == "screen_lock":
        timeout = condition.get("max_timeout_minutes", 15)
        actual = posture.get("screen_lock_timeout_minutes", 999)
        return actual <= timeout
    elif check_type == "jailbroken":
        return not posture.get("jailbroken", True)
    elif check_type == "certificate":
        return posture.get("certificate_valid", False)
    elif check_type == "agent_version":
        min_ver = condition.get("min_version", "0")
        actual = posture.get("agent_version", "0")
        return actual >= min_ver
    # Default: if we have no data, fail the check
    return False


def _ser(p: PosturePolicy) -> dict:
    return {"id": str(p.id), "name": p.name, "conditions": p.conditions,
            "grace_period_hours": p.grace_period_hours, "status": p.status,
            "created_at": str(p.created_at) if p.created_at else None}
