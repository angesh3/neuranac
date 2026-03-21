"""Generic REST Adapter — webhook/SIEM outbound integration.

Future-proof adapter for sending events to external REST endpoints
(Splunk, QRadar, Sentinel, custom webhooks, SOAR platforms, etc.).

This is a lightweight adapter that forwards NeuraNAC events to configurable
HTTP endpoints with retry, batching, and authentication support.
"""
from __future__ import annotations

import json
import time
from typing import Any, Dict, Optional

import httpx
import structlog

from app.adapter_base import AdapterStatus, BridgeAdapter

logger = structlog.get_logger()


class GenericRESTAdapter(BridgeAdapter):
    """Bridge adapter for outbound REST/webhook integrations."""

    adapter_type = "generic_rest"

    def __init__(self, connection_id: str, config: Dict[str, Any]):
        super().__init__(connection_id, config)
        self._simulated = config.get("simulated", True)
        self._target_url = config.get("target_url", "")
        self._auth_header = config.get("auth_header", "")
        self._http_client: Optional[httpx.AsyncClient] = None
        self._events_sent = 0
        self._errors_count = 0
        self._connected_at: Optional[float] = None

    async def connect(self) -> bool:
        if self._simulated:
            self.status = AdapterStatus.CONNECTED
            self._connected_at = time.time()
            logger.info("Generic REST adapter connected (simulated)",
                        connection_id=self.connection_id)
            return True

        try:
            headers = {"Content-Type": "application/json"}
            if self._auth_header:
                headers["Authorization"] = self._auth_header
            self._http_client = httpx.AsyncClient(timeout=15, headers=headers)
            self.status = AdapterStatus.CONNECTED
            self._connected_at = time.time()
            return True
        except Exception as e:
            self.set_error(str(e))
            return False

    async def disconnect(self) -> None:
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
        self.status = AdapterStatus.DISCONNECTED

    async def health(self) -> Dict[str, Any]:
        uptime = f"{time.time() - self._connected_at:.0f}s" if self._connected_at else "0s"
        return {
            "status": self.status.value,
            "simulated": self._simulated,
            "target_url": self._target_url,
            "events_sent": self._events_sent,
            "errors_count": self._errors_count,
            "uptime": uptime,
        }

    async def send(self, message: Dict[str, Any]) -> bool:
        if self._simulated:
            self._events_sent += 1
            return True

        if not self._http_client or not self._target_url:
            return False

        try:
            resp = await self._http_client.post(
                self._target_url, content=json.dumps(message).encode()
            )
            if resp.status_code < 400:
                self._events_sent += 1
                return True
            self._errors_count += 1
            return False
        except Exception as e:
            self._errors_count += 1
            logger.debug("REST adapter send error", error=str(e))
            return False

