"""UI Configuration endpoint — returns deployment mode, site info, and feature flags
so the frontend can conditionally render NeuraNAC nav, site selector, etc."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.config import get_settings
from app.database.session import get_db

router = APIRouter()


@router.get("/ui")
async def get_ui_config(db: AsyncSession = Depends(get_db)):
    """Returns deployment configuration for the frontend.

    Used by the web dashboard on mount to determine:
    - Whether to show NeuraNAC nav group (legacyNacEnabled)
    - Whether to show site selector (deploymentMode=hybrid)
    - Connector status (connectorConfigured)
    - Peer site info (peerConfigured)
    """
    settings = get_settings()

    # Fetch site info from DB if available
    site_name = "Local Site"
    peer_site_id = None
    peer_site_name = None
    connector_configured = False

    try:
        row = await db.execute(
            text("SELECT name FROM neuranac_sites WHERE id = :sid"),
            {"sid": settings.neuranac_site_id},
        )
        result = row.fetchone()
        if result:
            site_name = result[0]

        # Check for peer site
        if settings.deployment_mode == "hybrid":
            row = await db.execute(
                text("SELECT id, name FROM neuranac_sites WHERE id != :sid LIMIT 1"),
                {"sid": settings.neuranac_site_id},
            )
            peer = row.fetchone()
            if peer:
                peer_site_id = str(peer[0])
                peer_site_name = peer[1]

        # Check for connector
        if settings.legacy_nac_enabled:
            row = await db.execute(
                text("SELECT COUNT(*) FROM neuranac_connectors WHERE status != 'disconnected'")
            )
            count = row.scalar()
            connector_configured = (count or 0) > 0
    except Exception:
        pass  # Tables may not exist yet during first startup

    return {
        "deploymentMode": settings.deployment_mode,
        "siteType": settings.neuranac_site_type,
        "siteId": settings.neuranac_site_id,
        "siteName": site_name,
        "legacyNacEnabled": settings.legacy_nac_enabled,
        "peerConfigured": bool(settings.neuranac_peer_api_url),
        "peerApiUrl": settings.neuranac_peer_api_url or None,
        "peerSiteId": peer_site_id,
        "peerSiteName": peer_site_name,
        "connectorConfigured": connector_configured,
        "connectorUrl": settings.bridge_connector_url or None,
        "nodeId": settings.neuranac_node_id,
        "environment": settings.neuranac_env,
    }
