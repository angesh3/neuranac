"""Registration — self-registers the NeuraNAC Bridge with the cloud NeuraNAC API Gateway.

On startup, the bridge calls POST /api/v1/connectors/register on the cloud NeuraNAC.
Then sends periodic heartbeats to POST /api/v1/connectors/{id}/heartbeat.

Generalized from the old NeuraNAC-only registration to support any adapter type.
"""
import asyncio
from typing import Optional

import httpx
import structlog

from app.config import get_bridge_settings

logger = structlog.get_logger()


class BridgeRegistration:
    """Manages registration and heartbeat with the cloud NeuraNAC."""

    def __init__(self):
        self.settings = get_bridge_settings()
        self.connector_id: Optional[str] = None
        self._registered = False
        self._running = False
        self._events_relayed = 0
        self._errors_count = 0

    @property
    def is_registered(self) -> bool:
        return self._registered

    async def register(self) -> bool:
        """Register with cloud NeuraNAC. Retries until successful."""
        api_url = self.settings.cloud_neuranac_api_url
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"{api_url}/api/v1/connectors/register",
                    json={
                        "site_id": self.settings.site_id,
                        "name": self.settings.bridge_name,
                        "connector_type": "bridge",
                        "version": self.settings.bridge_version,
                        "metadata": {
                            "node_type": self.settings.node_type,
                            "site_type": self.settings.site_type,
                            "deployment_mode": self.settings.deployment_mode,
                            "tenant_id": self.settings.tenant_id,
                            "enabled_adapters": self.settings.enabled_adapters,
                        },
                    },
                )
                if resp.status_code in (200, 201):
                    data = resp.json()
                    self.connector_id = data.get("id")
                    self._registered = True
                    logger.info("Registered with cloud NeuraNAC",
                                connector_id=self.connector_id, api_url=api_url)
                    return True
                else:
                    logger.warning("Registration failed",
                                   status=resp.status_code, body=resp.text[:200])
                    return False
        except Exception as e:
            logger.warning("Registration error", error=str(e), api_url=api_url)
            return False

    async def start_heartbeat_loop(self):
        """Send heartbeats periodically until stopped."""
        self._running = True
        interval = self.settings.heartbeat_interval

        while self._running:
            if not self._registered:
                success = await self.register()
                if not success:
                    await asyncio.sleep(self.settings.registration_retry_interval)
                    continue

            try:
                api_url = self.settings.cloud_neuranac_api_url
                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.post(
                        f"{api_url}/api/v1/connectors/{self.connector_id}/heartbeat",
                        json={
                            "status": "connected",
                            "tunnel_status": "open",
                            "tunnel_latency_ms": 5,
                            "events_relayed": self._events_relayed,
                            "errors_count": self._errors_count,
                        },
                    )
                    if resp.status_code == 404:
                        logger.warning("Bridge not found on cloud, re-registering")
                        self._registered = False
                        self.connector_id = None
                        continue
            except Exception as e:
                logger.debug("Heartbeat failed", error=str(e))

            await asyncio.sleep(interval)

    async def stop(self):
        self._running = False

    def increment_events(self, count: int = 1):
        self._events_relayed += count

    def increment_errors(self, count: int = 1):
        self._errors_count += count

    def get_status(self) -> dict:
        return {
            "registered": self._registered,
            "connector_id": self.connector_id,
            "cloud_api_url": self.settings.cloud_neuranac_api_url,
            "events_relayed": self._events_relayed,
            "errors_count": self._errors_count,
        }


# Singleton
_registration: Optional[BridgeRegistration] = None


def get_registration() -> BridgeRegistration:
    global _registration
    if _registration is None:
        _registration = BridgeRegistration()
    return _registration
