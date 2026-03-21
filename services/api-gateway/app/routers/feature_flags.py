"""Feature flags router — CRUD and status for runtime feature toggles."""
from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update

from app.database.session import get_db
from app.models.admin import FeatureFlag
from app.services.feature_flags import FeatureFlagService

router = APIRouter()
_ff = FeatureFlagService()


class FlagUpdate(BaseModel):
    enabled: Optional[bool] = None
    rollout_percentage: Optional[int] = None
    tenant_filter: Optional[list] = None
    description: Optional[str] = None


@router.get("/")
async def list_feature_flags(db: AsyncSession = Depends(get_db)):
    """List all feature flags with their current state."""
    await _ff.load(db, force=True)
    return {"items": _ff.list_flags(), **_ff.get_stats()}


@router.get("/check/{flag_name}")
async def check_flag(
    flag_name: str,
    tenant_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Check if a specific flag is enabled for the given tenant."""
    await _ff.load(db)
    enabled = _ff.is_enabled(flag_name, tenant_id=tenant_id)
    return {"flag": flag_name, "enabled": enabled, "tenant_id": tenant_id}


@router.put("/{flag_name}")
async def update_flag(
    flag_name: str,
    body: FlagUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a feature flag's enabled state, rollout, or tenant filter."""
    result = await db.execute(select(FeatureFlag).where(FeatureFlag.name == flag_name))
    flag = result.scalar_one_or_none()
    if not flag:
        raise HTTPException(404, f"Flag '{flag_name}' not found")

    if body.enabled is not None:
        flag.enabled = body.enabled
    if body.rollout_percentage is not None:
        flag.rollout_percentage = body.rollout_percentage
    if body.tenant_filter is not None:
        flag.tenant_filter = body.tenant_filter
    if body.description is not None:
        flag.description = body.description

    await db.commit()
    _ff.load.__wrapped__ = None  # force cache invalidation
    await _ff.load(db, force=True)
    return {"status": "updated", "flag": flag_name, "enabled": flag.enabled}


class FlagCreate(BaseModel):
    name: str
    enabled: bool = False
    rollout_percentage: Optional[int] = 0
    description: Optional[str] = ""


@router.post("/", status_code=201)
async def create_flag(
    body: FlagCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new feature flag."""
    import uuid
    existing = await db.execute(select(FeatureFlag).where(FeatureFlag.name == body.name))
    existing_flag = existing.scalar_one_or_none()
    if existing_flag:
        from starlette.responses import JSONResponse
        return JSONResponse(status_code=409, content={"id": str(existing_flag.id), "detail": f"Flag '{body.name}' already exists"})

    flag = FeatureFlag(id=uuid.uuid4(), name=body.name, enabled=body.enabled,
                       rollout_percentage=body.rollout_percentage or 0,
                       description=body.description or "")
    db.add(flag)
    await db.commit()
    await _ff.load(db, force=True)
    return {"id": str(flag.id), "status": "created", "flag": body.name, "enabled": body.enabled}
