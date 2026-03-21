"""Cisco DNA Center (Catalyst Center) adapter for NeuraNAC Bridge.

Connects to the Cisco DNA Center REST API to synchronize network devices,
fabric sites, and SDA policies. Publishes events to NATS.

Requires: DNAC_HOST, DNAC_USERNAME, DNAC_PASSWORD environment variables.
"""
import os
import time
import structlog
from typing import Any, Dict, List, Optional

from app.adapter_base import BridgeAdapter, AdapterStatus

logger = structlog.get_logger()

DNAC_HOST = os.getenv("DNAC_HOST", "")
DNAC_USERNAME = os.getenv("DNAC_USERNAME", "admin")
DNAC_PASSWORD = os.getenv("DNAC_PASSWORD", "")
DNAC_VERIFY_SSL = os.getenv("DNAC_VERIFY_SSL", "false").lower() == "true"


class DNACAdapter(BridgeAdapter):
    """Adapter for Cisco DNA Center / Catalyst Center integration."""

    adapter_type = "dnac"

    def __init__(self, connection_id: str, config: Dict[str, Any]):
        super().__init__(connection_id, config)
        self._host = config.get("host") or DNAC_HOST
        self._username = config.get("username") or DNAC_USERNAME
        self._password = config.get("password") or DNAC_PASSWORD
        self._verify_ssl = config.get("verify_ssl", DNAC_VERIFY_SSL)
        self._token: Optional[str] = None
        self._token_expiry: float = 0
        self._client = None
        self._poll_interval = int(config.get("poll_interval_seconds", 300))
        self._last_poll: float = 0
        self._stats = {
            "devices_synced": 0,
            "sites_synced": 0,
            "fabrics_synced": 0,
            "errors": 0,
        }

    async def connect(self) -> bool:
        """Authenticate to DNA Center and establish a session."""
        if not self._host:
            self.set_error("DNAC_HOST not configured")
            return False
        try:
            import httpx
            self._client = httpx.AsyncClient(
                base_url=f"https://{self._host}",
                verify=self._verify_ssl,
                timeout=30,
            )
            # Authenticate via /dna/system/api/v1/auth/token
            auth_resp = await self._client.post(
                "/dna/system/api/v1/auth/token",
                auth=(self._username, self._password),
            )
            if auth_resp.status_code != 200:
                self.set_error(f"DNAC auth failed: HTTP {auth_resp.status_code}")
                return False

            data = auth_resp.json()
            self._token = data.get("Token")
            self._token_expiry = time.time() + 3600  # DNAC tokens last ~1h
            self._client.headers["X-Auth-Token"] = self._token

            self.status = AdapterStatus.CONNECTED
            logger.info("DNAC adapter connected", host=self._host)
            return True
        except Exception as e:
            self.set_error(str(e))
            logger.error("DNAC connect failed", error=str(e))
            return False

    async def disconnect(self) -> None:
        """Close DNAC API client."""
        if self._client:
            await self._client.aclose()
            self._client = None
        self._token = None
        self.status = AdapterStatus.DISCONNECTED
        logger.info("DNAC adapter disconnected", connection_id=self.connection_id)

    async def health(self) -> Dict[str, Any]:
        """Return health and sync statistics."""
        token_valid = self._token is not None and time.time() < self._token_expiry
        return {
            **self.get_status(),
            "host": self._host,
            "token_valid": token_valid,
            "token_expires_in": max(0, int(self._token_expiry - time.time())) if token_valid else 0,
            "poll_interval_seconds": self._poll_interval,
            "last_poll": self._last_poll,
            "stats": self._stats,
        }

    async def send(self, message: Dict[str, Any]) -> bool:
        """Send a command to DNA Center (e.g., push SDA policy, provision device)."""
        if not self._client or self.status != AdapterStatus.CONNECTED:
            return False

        # Refresh token if expired
        if time.time() >= self._token_expiry:
            if not await self._refresh_token():
                return False

        action = message.get("action", "")
        try:
            if action == "sync_now":
                return await self._full_sync()
            elif action == "provision_device":
                return await self._provision_device(message)
            elif action == "update_sda_policy":
                return await self._update_sda_policy(message)
            else:
                logger.warning("Unknown DNAC action", action=action)
                return False
        except Exception as e:
            self._stats["errors"] += 1
            logger.error("DNAC send failed", action=action, error=str(e))
            return False

    async def on_message(self, message: Dict[str, Any]) -> None:
        """Handle inbound events from DNAC (webhook subscriptions)."""
        event_type = message.get("eventId", message.get("type", "unknown"))
        logger.info("DNAC event received", type=event_type)

    async def _refresh_token(self) -> bool:
        """Re-authenticate to get a fresh token."""
        try:
            auth_resp = await self._client.post(
                "/dna/system/api/v1/auth/token",
                auth=(self._username, self._password),
            )
            if auth_resp.status_code == 200:
                self._token = auth_resp.json().get("Token")
                self._token_expiry = time.time() + 3600
                self._client.headers["X-Auth-Token"] = self._token
                return True
            self.set_error(f"Token refresh failed: HTTP {auth_resp.status_code}")
            return False
        except Exception as e:
            self.set_error(f"Token refresh error: {e}")
            return False

    async def _full_sync(self) -> bool:
        """Sync devices, sites, and fabric domains from DNAC."""
        if not self._client:
            return False
        try:
            # Sync network devices
            resp = await self._client.get("/dna/intent/api/v1/network-device")
            if resp.status_code == 200:
                devices = resp.json().get("response", [])
                self._stats["devices_synced"] = len(devices)
                logger.info("DNAC devices synced", count=len(devices))

            # Sync sites
            resp = await self._client.get("/dna/intent/api/v1/site")
            if resp.status_code == 200:
                sites = resp.json().get("response", [])
                self._stats["sites_synced"] = len(sites)

            # Sync SDA fabric domains
            resp = await self._client.get("/dna/intent/api/v1/business/sda/fabric")
            if resp.status_code == 200:
                fabrics = resp.json().get("response", [])
                self._stats["fabrics_synced"] = len(fabrics) if isinstance(fabrics, list) else 1

            self._last_poll = time.time()
            return True
        except Exception as e:
            self._stats["errors"] += 1
            logger.error("DNAC sync error", error=str(e))
            return False

    async def _provision_device(self, message: Dict[str, Any]) -> bool:
        """Trigger device provisioning in DNAC."""
        device_ip = message.get("device_ip", "")
        site_name = message.get("site_name", "")
        if not device_ip:
            return False
        resp = await self._client.post(
            "/dna/intent/api/v1/business/sda/provision-device",
            json={"deviceManagementIpAddress": device_ip, "siteNameHierarchy": site_name},
        )
        return resp.status_code in (200, 202)

    async def _update_sda_policy(self, message: Dict[str, Any]) -> bool:
        """Push an SDA access policy update."""
        policy_data = message.get("policy_data", {})
        if not policy_data:
            return False
        resp = await self._client.put(
            "/dna/intent/api/v1/business/sda/authentication-profile",
            json=policy_data,
        )
        return resp.status_code in (200, 202)
