"""Feature flag service — runtime feature toggling backed by the DB.

Loads flags from the ``feature_flags`` table, caches them in memory, and
exposes helpers that routers and middleware can use to gate functionality.

Usage:
    from app.services.feature_flags import FeatureFlagService, require_flag

    ff = FeatureFlagService()
    await ff.load(db)
    if ff.is_enabled("shadow_ai_detection"):
        ...

    # FastAPI dependency — raises 404 when flag is off
    @router.get("/shadow", dependencies=[Depends(require_flag("shadow_ai_detection"))])
    async def shadow_endpoint(): ...
"""
import random
import time
import structlog
from typing import Dict, Optional, Any, List
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

logger = structlog.get_logger()

_CACHE_TTL_SECONDS = 30


class FeatureFlagService:
    """In-process feature flag evaluator backed by PostgreSQL."""

    _instance: Optional["FeatureFlagService"] = None

    def __new__(cls) -> "FeatureFlagService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):
            self._initialized = True
            self._flags: Dict[str, dict] = {}
            self._loaded_at: float = 0

    async def load(self, db: AsyncSession, force: bool = False) -> None:
        """Load or refresh flags from the database."""
        if not force and self._flags and (time.time() - self._loaded_at < _CACHE_TTL_SECONDS):
            return
        try:
            from app.models.admin import FeatureFlag
            result = await db.execute(select(FeatureFlag))
            rows = result.scalars().all()
            self._flags = {
                r.name: {
                    "enabled": r.enabled,
                    "rollout_percentage": r.rollout_percentage or 0,
                    "tenant_filter": r.tenant_filter or [],
                    "description": r.description or "",
                }
                for r in rows
            }
            self._loaded_at = time.time()
            logger.info("Feature flags loaded", count=len(self._flags))
        except Exception as e:
            logger.warning("Feature flag load failed, using cache", error=str(e))

    def is_enabled(
        self,
        flag_name: str,
        tenant_id: Optional[str] = None,
        default: bool = False,
    ) -> bool:
        """Check whether a feature flag is enabled.

        Evaluation order:
        1. If the flag doesn't exist, return *default*.
        2. If ``enabled`` is False, return False.
        3. If a ``tenant_filter`` list exists and the caller's tenant isn't in
           it, return False.
        4. If ``rollout_percentage`` < 100, do a deterministic coin flip
           seeded on (flag_name, tenant_id) so the same tenant always gets the
           same answer for a given flag.
        """
        flag = self._flags.get(flag_name)
        if flag is None:
            return default
        if not flag["enabled"]:
            return False
        # Tenant filter
        tf = flag.get("tenant_filter", [])
        if tf and tenant_id and tenant_id not in tf:
            return False
        # Rollout percentage
        pct = flag.get("rollout_percentage", 100)
        if pct is not None and pct < 100:
            seed = hash(f"{flag_name}:{tenant_id or ''}")
            return (seed % 100) < pct
        return True

    def list_flags(self) -> List[Dict[str, Any]]:
        """Return all loaded flags as a list of dicts."""
        return [
            {"name": name, **data}
            for name, data in sorted(self._flags.items())
        ]

    def get_stats(self) -> Dict[str, Any]:
        enabled = sum(1 for f in self._flags.values() if f["enabled"])
        return {
            "total": len(self._flags),
            "enabled": enabled,
            "disabled": len(self._flags) - enabled,
            "cache_age_seconds": round(time.time() - self._loaded_at, 1) if self._loaded_at else None,
        }


def require_flag(flag_name: str, default: bool = False):
    """FastAPI dependency that returns 404 when a flag is disabled."""
    from fastapi import HTTPException, Depends
    from app.database.session import get_db

    async def _check(db: AsyncSession = Depends(get_db)):
        ff = FeatureFlagService()
        await ff.load(db)
        if not ff.is_enabled(flag_name, default=default):
            raise HTTPException(status_code=404, detail=f"Feature '{flag_name}' is not enabled")

    return _check
