"""Tamper-proof audit log hash chain service.

Computes SHA-256 hashes for each audit entry, linking each to the previous
entry's hash to form an immutable chain. Provides verification and repair.

Usage:
    from app.services.audit_chain import AuditChainService
    svc = AuditChainService()
    entry_hash, prev_hash = await svc.compute_chain_hashes(db, entry_data)
"""
import hashlib
import json
import structlog
from typing import Optional, Tuple, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text

logger = structlog.get_logger()


class AuditChainService:
    """Manages tamper-proof hash chain for audit log entries."""

    _instance: Optional["AuditChainService"] = None

    def __new__(cls) -> "AuditChainService":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if not hasattr(self, "_initialized"):
            self._initialized = True
            self._last_hash: Optional[str] = None

    @staticmethod
    def _compute_hash(data: Dict[str, Any], prev_hash: str = "") -> str:
        """Compute SHA-256 hash of an audit entry, chained to the previous hash.

        The canonical form includes: actor, action, entity_type, entity_id,
        before_data, after_data, source_ip, timestamp, and prev_hash.
        """
        canonical = json.dumps(
            {
                "actor": data.get("actor", ""),
                "action": data.get("action", ""),
                "entity_type": data.get("entity_type", ""),
                "entity_id": data.get("entity_id", ""),
                "before_data": data.get("before_data"),
                "after_data": data.get("after_data"),
                "source_ip": data.get("source_ip", ""),
                "timestamp": str(data.get("timestamp", "")),
                "prev_hash": prev_hash,
            },
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    async def get_last_hash(self, db: AsyncSession) -> str:
        """Retrieve the entry_hash of the most recent audit log row."""
        if self._last_hash is not None:
            return self._last_hash
        from app.models.admin import AuditLog

        result = await db.execute(
            select(AuditLog.entry_hash)
            .where(AuditLog.entry_hash.isnot(None))
            .order_by(AuditLog.timestamp.desc())
            .limit(1)
        )
        row = result.scalar_one_or_none()
        self._last_hash = row or ""
        return self._last_hash

    async def compute_chain_hashes(
        self, db: AsyncSession, entry_data: Dict[str, Any]
    ) -> Tuple[str, str]:
        """Compute (entry_hash, prev_hash) for a new audit entry.

        Returns:
            Tuple of (entry_hash, prev_hash) to store on the new AuditLog row.
        """
        prev_hash = await self.get_last_hash(db)
        entry_hash = self._compute_hash(entry_data, prev_hash)
        self._last_hash = entry_hash
        return entry_hash, prev_hash

    async def verify_chain(
        self, db: AsyncSession, limit: int = 10000
    ) -> Dict[str, Any]:
        """Verify the integrity of the audit log hash chain.

        Returns a dict with chain_valid, entries_checked, first_broken_id, and
        a list of broken entries (up to 10).
        """
        from app.models.admin import AuditLog

        result = await db.execute(
            select(AuditLog).order_by(AuditLog.timestamp).limit(limit)
        )
        logs = result.scalars().all()

        if not logs:
            return {"chain_valid": True, "entries_checked": 0, "broken": []}

        broken = []
        prev_hash = ""

        for i, log in enumerate(logs):
            if log.entry_hash is None:
                continue

            if log.prev_hash is not None and log.prev_hash != prev_hash:
                broken.append(
                    {
                        "id": str(log.id),
                        "index": i,
                        "expected_prev": prev_hash,
                        "actual_prev": log.prev_hash,
                    }
                )
                if len(broken) >= 10:
                    break

            entry_data = {
                "actor": log.actor,
                "action": log.action,
                "entity_type": log.entity_type,
                "entity_id": log.entity_id,
                "before_data": log.before_data,
                "after_data": log.after_data,
                "source_ip": log.source_ip,
                "timestamp": log.timestamp,
            }
            expected_hash = self._compute_hash(entry_data, log.prev_hash or "")
            if log.entry_hash != expected_hash:
                broken.append(
                    {
                        "id": str(log.id),
                        "index": i,
                        "expected_hash": expected_hash,
                        "actual_hash": log.entry_hash,
                        "tampered": True,
                    }
                )
                if len(broken) >= 10:
                    break

            prev_hash = log.entry_hash

        return {
            "chain_valid": len(broken) == 0,
            "entries_checked": len(logs),
            "broken": broken,
            "first_broken_id": broken[0]["id"] if broken else None,
        }

    async def backfill_hashes(self, db: AsyncSession, batch_size: int = 500) -> int:
        """Backfill entry_hash and prev_hash for rows missing them.

        Returns the number of rows updated.
        """
        from app.models.admin import AuditLog

        result = await db.execute(
            select(AuditLog)
            .where(AuditLog.entry_hash.is_(None))
            .order_by(AuditLog.timestamp)
            .limit(batch_size)
        )
        logs = result.scalars().all()

        if not logs:
            return 0

        prev_hash = await self.get_last_hash(db)
        updated = 0

        for log in logs:
            entry_data = {
                "actor": log.actor,
                "action": log.action,
                "entity_type": log.entity_type,
                "entity_id": log.entity_id,
                "before_data": log.before_data,
                "after_data": log.after_data,
                "source_ip": log.source_ip,
                "timestamp": log.timestamp,
            }
            entry_hash = self._compute_hash(entry_data, prev_hash)
            log.prev_hash = prev_hash
            log.entry_hash = entry_hash
            prev_hash = entry_hash
            updated += 1

        self._last_hash = prev_hash
        await db.commit()
        logger.info("Audit chain backfill complete", updated=updated)
        return updated

    def invalidate_cache(self):
        """Reset cached last_hash so next call re-fetches from DB."""
        self._last_hash = None
