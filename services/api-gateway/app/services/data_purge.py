"""Data retention purge service.

Implements scheduled cleanup of expired data based on configurable retention
policies per data category (sessions, audit logs, guest accounts, etc.).
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger("neuranac.data_purge")


@dataclass
class RetentionPolicy:
    """Defines a data retention rule."""
    table: str
    timestamp_column: str = "created_at"
    retention_days: int = 90
    condition: str = ""          # extra WHERE clause
    batch_size: int = 1000
    description: str = ""


# Default retention policies — can be overridden by DB config
DEFAULT_POLICIES: List[RetentionPolicy] = [
    RetentionPolicy(
        table="radius_session_log",
        timestamp_column="created_at",
        retention_days=90,
        description="RADIUS session logs older than 90 days",
    ),
    RetentionPolicy(
        table="audit_logs",
        timestamp_column="created_at",
        retention_days=365,
        description="Audit logs older than 1 year",
    ),
    RetentionPolicy(
        table="internal_users",
        timestamp_column="created_at",
        retention_days=7,
        condition="status = 'guest'",
        description="Expired guest accounts older than 7 days",
    ),
    RetentionPolicy(
        table="ai_endpoint_profiles",
        timestamp_column="updated_at",
        retention_days=180,
        description="AI endpoint profiles not updated in 180 days",
    ),
    RetentionPolicy(
        table="ai_risk_scores",
        timestamp_column="computed_at",
        retention_days=90,
        description="AI risk scores older than 90 days",
    ),
    RetentionPolicy(
        table="ai_anomaly_events",
        timestamp_column="detected_at",
        retention_days=90,
        description="AI anomaly events older than 90 days",
    ),
    RetentionPolicy(
        table="ai_policy_drift",
        timestamp_column="recorded_at",
        retention_days=60,
        description="Policy drift records older than 60 days",
    ),
    RetentionPolicy(
        table="legacy_nac_sync_log",
        timestamp_column="synced_at",
        retention_days=90,
        description="NeuraNAC sync log entries older than 90 days",
    ),
    RetentionPolicy(
        table="legacy_nac_event_stream_events",
        timestamp_column="received_at",
        retention_days=30,
        description="Event Stream events older than 30 days",
    ),
    RetentionPolicy(
        table="privacy_consent_log",
        timestamp_column="consented_at",
        retention_days=730,
        condition="withdrawn = true",
        description="Withdrawn privacy consents older than 2 years",
    ),
]


@dataclass
class PurgeResult:
    """Result of a single purge operation."""
    table: str
    rows_deleted: int
    duration_ms: float
    error: Optional[str] = None


class DataPurgeService:
    """Scheduled data retention purge service."""

    def __init__(self, policies: Optional[List[RetentionPolicy]] = None):
        self._policies = policies or DEFAULT_POLICIES
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._last_run: Optional[datetime] = None
        self._last_results: List[PurgeResult] = []

    @property
    def policies(self) -> List[RetentionPolicy]:
        return self._policies

    @property
    def last_run(self) -> Optional[datetime]:
        return self._last_run

    @property
    def last_results(self) -> List[PurgeResult]:
        return self._last_results

    async def run_purge(self, db: AsyncSession) -> List[PurgeResult]:
        """Execute all configured purge policies."""
        results = []
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        logger.info("Starting data purge run with %d policies", len(self._policies))

        for policy in self._policies:
            result = await self._purge_table(db, policy, now)
            results.append(result)
            if result.error:
                logger.error("Purge error for %s: %s", policy.table, result.error)
            elif result.rows_deleted > 0:
                logger.info("Purged %d rows from %s (%s)",
                            result.rows_deleted, policy.table, policy.description)

        await db.commit()
        self._last_run = now
        self._last_results = results

        total_deleted = sum(r.rows_deleted for r in results)
        logger.info("Data purge complete: %d total rows deleted across %d tables",
                     total_deleted, len(results))
        return results

    async def _purge_table(
        self, db: AsyncSession, policy: RetentionPolicy, now: datetime
    ) -> PurgeResult:
        """Purge expired rows from a single table in batches."""
        import time
        start = time.monotonic()
        total_deleted = 0

        try:
            # Check if table exists first
            check = await db.execute(text(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = :t)"
            ), {"t": policy.table})
            exists = check.scalar()
            if not exists:
                return PurgeResult(
                    table=policy.table, rows_deleted=0,
                    duration_ms=(time.monotonic() - start) * 1000,
                    error=f"table {policy.table} does not exist",
                )

            # Build DELETE query with retention window
            cutoff = f"NOW() - INTERVAL '{policy.retention_days} days'"
            where = f"{policy.timestamp_column} < {cutoff}"
            if policy.condition:
                where = f"{where} AND {policy.condition}"

            # Delete in batches to avoid long-running transactions
            while True:
                result = await db.execute(text(
                    f"DELETE FROM {policy.table} "
                    f"WHERE ctid IN ("
                    f"  SELECT ctid FROM {policy.table} "
                    f"  WHERE {where} LIMIT :batch"
                    f")"
                ), {"batch": policy.batch_size})

                deleted = result.rowcount
                total_deleted += deleted

                if deleted < policy.batch_size:
                    break

                # Yield control between batches
                await asyncio.sleep(0.01)

        except Exception as e:
            return PurgeResult(
                table=policy.table, rows_deleted=total_deleted,
                duration_ms=(time.monotonic() - start) * 1000,
                error=str(e),
            )

        return PurgeResult(
            table=policy.table, rows_deleted=total_deleted,
            duration_ms=(time.monotonic() - start) * 1000,
        )

    async def start_scheduler(self, db_factory, interval_hours: int = 24):
        """Start the background purge scheduler."""
        if self._running:
            return

        self._running = True
        self._task = asyncio.create_task(self._scheduler_loop(db_factory, interval_hours))
        logger.info("Data purge scheduler started (interval=%dh)", interval_hours)

    async def _scheduler_loop(self, db_factory, interval_hours: int):
        """Background loop that runs purge at the configured interval."""
        while self._running:
            try:
                async with db_factory() as db:
                    await self.run_purge(db)
            except Exception as e:
                logger.error("Scheduled purge failed: %s", e)

            # Sleep until next run
            await asyncio.sleep(interval_hours * 3600)

    async def stop_scheduler(self):
        """Stop the background purge scheduler."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        logger.info("Data purge scheduler stopped")

    def get_status(self) -> Dict:
        """Get current purge service status."""
        return {
            "running": self._running,
            "last_run": self._last_run.isoformat() if self._last_run else None,
            "policies_count": len(self._policies),
            "last_results": [
                {
                    "table": r.table,
                    "rows_deleted": r.rows_deleted,
                    "duration_ms": round(r.duration_ms, 2),
                    "error": r.error,
                }
                for r in self._last_results
            ] if self._last_results else [],
        }


# Singleton
_purge_service: Optional[DataPurgeService] = None


def get_purge_service() -> DataPurgeService:
    """Get the global data purge service instance."""
    global _purge_service
    if _purge_service is None:
        _purge_service = DataPurgeService()
    return _purge_service
