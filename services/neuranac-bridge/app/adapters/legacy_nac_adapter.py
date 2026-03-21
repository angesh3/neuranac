"""Legacy NAC Adapter — integration with external legacy NAC systems.

Handles REST/ERS sync and event-stream connectivity for coexistence and migration.
Supports simulated mode for development and testing.
"""
from __future__ import annotations

import time
from typing import Any, Dict

import structlog

from app.adapter_base import AdapterStatus, BridgeAdapter

logger = structlog.get_logger()


class LegacyNacAdapter(BridgeAdapter):
    """Bridge adapter for legacy NAC (REST/ERS + event-stream) integration."""

    adapter_type = "legacy_nac"

    def __init__(self, connection_id: str, config: Dict[str, Any]):
        super().__init__(connection_id, config)
        self._simulated = config.get("simulated", True)
        self._hostname = config.get("legacy_nac_hostname", "legacy-nac.local")
        self._connected_at: float | None = None
        self._events_count = 0

    async def connect(self) -> bool:
        if self._simulated:
            self.status = AdapterStatus.CONNECTED
            self._connected_at = time.time()
            logger.info("Legacy NAC adapter connected (simulated)",
                        connection_id=self.connection_id,
                        hostname=self._hostname)
            return True
        # TODO: implement real REST/ERS + event-stream connection
        self.set_error("Non-simulated legacy NAC connection not yet implemented")
        return False

    async def disconnect(self) -> None:
        self.status = AdapterStatus.DISCONNECTED
        self._connected_at = None
        logger.info("Legacy NAC adapter disconnected", connection_id=self.connection_id)

    async def health(self) -> Dict[str, Any]:
        uptime = f"{time.time() - self._connected_at:.0f}s" if self._connected_at else "0s"
        return {
            "status": self.status.value,
            "simulated": self._simulated,
            "legacy_nac_hostname": self._hostname,
            "events_count": self._events_count,
            "uptime": uptime,
        }

    async def send(self, message: Dict[str, Any]) -> bool:
        if self._simulated:
            self._events_count += 1
            return True
        return False
