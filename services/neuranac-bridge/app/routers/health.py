"""Health and status endpoints for the NeuraNAC Bridge service."""
from fastapi import APIRouter

from app.config import get_bridge_settings
from app.connection_manager import get_connection_manager

router = APIRouter()


@router.get("/health")
async def health():
    """Basic health check."""
    settings = get_bridge_settings()
    manager = get_connection_manager()

    return {
        "status": "healthy",
        "service": "neuranac-bridge",
        "bridge_name": settings.bridge_name,
        "version": settings.bridge_version,
        "site_id": settings.site_id,
        "tenant_id": settings.tenant_id,
        "site_type": settings.site_type,
        "deployment_mode": settings.deployment_mode,
        "simulated": settings.simulated,
        "connection_count": manager.connection_count,
    }


@router.get("/ready")
async def readiness():
    """Readiness probe — checks if at least one adapter is connected."""
    manager = get_connection_manager()
    agg = await manager.health()
    ready = agg["connection_count"] > 0 or get_bridge_settings().simulated
    return {
        "ready": ready,
        "connections": agg["connection_count"],
    }


@router.get("/status")
async def detailed_status():
    """Detailed status of all Bridge subsystems."""
    settings = get_bridge_settings()
    manager = get_connection_manager()
    agg = await manager.health()

    return {
        "bridge": {
            "name": settings.bridge_name,
            "version": settings.bridge_version,
            "site_id": settings.site_id,
            "tenant_id": settings.tenant_id,
            "site_type": settings.site_type,
            "deployment_mode": settings.deployment_mode,
            "simulated": settings.simulated,
            "enabled_adapters": settings.enabled_adapters,
        },
        "connections": agg,
    }
