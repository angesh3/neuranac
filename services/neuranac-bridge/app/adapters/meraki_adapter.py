"""Meraki Dashboard API adapter for NeuraNAC Bridge.

Connects to the Cisco Meraki cloud dashboard API to synchronize
network devices, clients, and group policies. Publishes events to NATS.

Requires: MERAKI_API_KEY environment variable.
"""
import os
import time
import structlog
from typing import Any, Dict, List, Optional

from app.adapter_base import BridgeAdapter, AdapterStatus

logger = structlog.get_logger()

MERAKI_BASE_URL = os.getenv("MERAKI_BASE_URL", "https://api.meraki.com/api/v1")
MERAKI_API_KEY = os.getenv("MERAKI_API_KEY", "")


class MerakiAdapter(BridgeAdapter):
    """Adapter for Cisco Meraki Dashboard API integration."""

    adapter_type = "meraki"

    def __init__(self, connection_id: str, config: Dict[str, Any]):
        super().__init__(connection_id, config)
        self._api_key = config.get("api_key") or MERAKI_API_KEY
        self._org_id = config.get("organization_id", "")
        self._network_ids: List[str] = config.get("network_ids", [])
        self._client = None
        self._poll_interval = int(config.get("poll_interval_seconds", 300))
        self._last_poll: float = 0
        self._stats = {
            "networks_synced": 0,
            "devices_synced": 0,
            "clients_synced": 0,
            "errors": 0,
        }

    async def connect(self) -> bool:
        """Establish connection to Meraki Dashboard API."""
        if not self._api_key:
            self.set_error("MERAKI_API_KEY not configured")
            return False
        try:
            import httpx
            self._client = httpx.AsyncClient(
                base_url=MERAKI_BASE_URL,
                headers={
                    "X-Cisco-Meraki-API-Key": self._api_key,
                    "Content-Type": "application/json",
                },
                timeout=30,
            )
            # Validate API key by fetching organizations
            resp = await self._client.get("/organizations")
            if resp.status_code != 200:
                self.set_error(f"Meraki API auth failed: HTTP {resp.status_code}")
                return False

            orgs = resp.json()
            if not self._org_id and orgs:
                self._org_id = orgs[0]["id"]
                logger.info("Meraki auto-selected org", org_id=self._org_id, org_name=orgs[0].get("name"))

            # Discover networks if none specified
            if not self._network_ids:
                net_resp = await self._client.get(f"/organizations/{self._org_id}/networks")
                if net_resp.status_code == 200:
                    self._network_ids = [n["id"] for n in net_resp.json()]

            self.status = AdapterStatus.CONNECTED
            logger.info("Meraki adapter connected",
                        org_id=self._org_id, networks=len(self._network_ids))
            return True
        except Exception as e:
            self.set_error(str(e))
            logger.error("Meraki connect failed", error=str(e))
            return False

    async def disconnect(self) -> None:
        """Close Meraki API client."""
        if self._client:
            await self._client.aclose()
            self._client = None
        self.status = AdapterStatus.DISCONNECTED
        logger.info("Meraki adapter disconnected", connection_id=self.connection_id)

    async def health(self) -> Dict[str, Any]:
        """Return health and sync statistics."""
        return {
            **self.get_status(),
            "organization_id": self._org_id,
            "network_count": len(self._network_ids),
            "poll_interval_seconds": self._poll_interval,
            "last_poll": self._last_poll,
            "stats": self._stats,
        }

    async def send(self, message: Dict[str, Any]) -> bool:
        """Send a command to Meraki (e.g., update group policy, push SSID config)."""
        if not self._client or self.status != AdapterStatus.CONNECTED:
            return False
        action = message.get("action", "")
        try:
            if action == "update_group_policy":
                return await self._update_group_policy(message)
            elif action == "sync_now":
                return await self._full_sync()
            else:
                logger.warning("Unknown Meraki action", action=action)
                return False
        except Exception as e:
            self._stats["errors"] += 1
            logger.error("Meraki send failed", action=action, error=str(e))
            return False

    async def on_message(self, message: Dict[str, Any]) -> None:
        """Handle inbound webhook events from Meraki (if configured)."""
        event_type = message.get("alertType", message.get("type", "unknown"))
        logger.info("Meraki webhook event", type=event_type, network=message.get("networkId"))

    async def _full_sync(self) -> bool:
        """Sync devices and clients from all configured networks."""
        if not self._client:
            return False
        for net_id in self._network_ids:
            try:
                # Sync devices
                resp = await self._client.get(f"/networks/{net_id}/devices")
                if resp.status_code == 200:
                    self._stats["devices_synced"] += len(resp.json())

                # Sync clients (last 24h)
                resp = await self._client.get(f"/networks/{net_id}/clients", params={"timespan": 86400})
                if resp.status_code == 200:
                    self._stats["clients_synced"] += len(resp.json())

                self._stats["networks_synced"] += 1
            except Exception as e:
                self._stats["errors"] += 1
                logger.error("Meraki sync error", network=net_id, error=str(e))

        self._last_poll = time.time()
        logger.info("Meraki sync complete", stats=self._stats)
        return True

    async def _update_group_policy(self, message: Dict[str, Any]) -> bool:
        """Push a group policy update to a Meraki network."""
        network_id = message.get("network_id", self._network_ids[0] if self._network_ids else "")
        policy_id = message.get("policy_id", "")
        policy_data = message.get("policy_data", {})
        if not network_id or not policy_id:
            return False
        resp = await self._client.put(
            f"/networks/{network_id}/groupPolicies/{policy_id}",
            json=policy_data,
        )
        return resp.status_code == 200
