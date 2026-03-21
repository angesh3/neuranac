"""Licensing and usage metering router"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.database.session import get_db

router = APIRouter()


@router.get("/")
async def get_license_info(db: AsyncSession = Depends(get_db)):
    from app.models.admin import Tenant
    result = await db.execute(select(Tenant).limit(1))
    tenant = result.scalar_one_or_none()
    return {
        "tier": "essentials",
        "license_type": "trial",
        "max_endpoints": 100,
        "features": {"ai_engine": True, "twin_node": True, "shadow_ai": True},
        "valid_from": None,
        "valid_to": None,
        "status": "active",
    }


@router.get("/usage")
async def get_usage(db: AsyncSession = Depends(get_db)):
    return {
        "endpoint_count": 0,
        "compute_hours": 0,
        "ai_queries": 0,
        "bandwidth_gb": 0,
        "date": None,
    }


@router.post("/activate")
async def activate_license(data: dict):
    license_key = data.get("license_key", "")
    return {"status": "activated" if license_key else "invalid_key", "tier": "essentials"}


@router.get("/tiers")
async def list_tiers():
    return {
        "tiers": [
            {"name": "essentials", "max_endpoints": 100, "features": ["radius", "tacacs", "basic_policy"]},
            {"name": "advantage", "max_endpoints": 5000, "features": ["radius", "tacacs", "advanced_policy", "guest", "posture", "profiling"]},
            {"name": "premier", "max_endpoints": 50000, "features": ["all", "ai_engine", "twin_node", "shadow_ai", "nlp_policy"]},
        ]
    }
