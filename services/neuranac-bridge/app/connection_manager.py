"""Connection Manager — core orchestrator for all Bridge adapters.

Responsibilities:
  1. Maintain a registry of active connections (adapter instances)
  2. Spawn/stop adapters based on config or API calls
  3. Aggregate health from all adapters
  4. Route messages between adapters and local NeuraNAC services
  5. Auto-discover adapters from config on startup
  6. Enforce mTLS when bridge_trust_enforce is enabled
"""
from __future__ import annotations

import asyncio
import os
import ssl
from typing import Any, Dict, List, Optional, Type

import structlog

from app.adapter_base import AdapterStatus, BridgeAdapter
from app.config import get_bridge_settings

logger = structlog.get_logger()


def build_mtls_ssl_context(settings) -> Optional[ssl.SSLContext]:
    """Build an SSL context using per-tenant mTLS certs issued during activation.

    Returns None if mTLS is not configured or cert files are missing.
    Raises RuntimeError if bridge_trust_enforce is True but certs are absent.
    """
    cert_path = settings.client_cert_path
    key_path = settings.client_key_path
    ca_path = settings.ca_cert_path

    has_certs = (
        cert_path and os.path.isfile(cert_path)
        and key_path and os.path.isfile(key_path)
    )

    if not has_certs:
        if settings.bridge_trust_enforce:
            raise RuntimeError(
                "mTLS enforcement is enabled (BRIDGE_TRUST_ENFORCE=true) but "
                f"client certs are missing: cert={cert_path!r}, key={key_path!r}. "
                "Run connector activation to obtain certificates first."
            )
        return None

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.load_cert_chain(certfile=cert_path, keyfile=key_path)
    if ca_path and os.path.isfile(ca_path):
        ctx.load_verify_locations(cafile=ca_path)
    else:
        # If no CA cert, don't verify server cert (dev mode)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    logger.info("mTLS SSL context built", cert=cert_path, ca=ca_path)
    return ctx

# Global adapter type registry — populated lazily to avoid circular imports
_adapter_classes: Dict[str, Type[BridgeAdapter]] = {}
_adapters_discovered = False


def _discover_adapters() -> None:
    """Lazily import and register all adapter classes to avoid circular imports."""
    global _adapters_discovered
    if _adapters_discovered:
        return
    _adapters_discovered = True
    from app.adapters.meraki_adapter import MerakiAdapter
    from app.adapters.dnac_adapter import DNACAdapter
    from app.adapters.legacy_nac_adapter import LegacyNacAdapter
    from app.adapters.neuranac_to_neuranac_adapter import NeuraNACToNeuraNACAdapter
    from app.adapters.generic_rest_adapter import GenericRESTAdapter
    _adapter_classes.setdefault("meraki", MerakiAdapter)
    _adapter_classes.setdefault("dnac", DNACAdapter)
    _adapter_classes.setdefault("legacy_nac", LegacyNacAdapter)
    _adapter_classes.setdefault("neuranac_to_neuranac", NeuraNACToNeuraNACAdapter)
    _adapter_classes.setdefault("generic_rest", GenericRESTAdapter)


def register_adapter_class(adapter_type: str, cls: Type[BridgeAdapter]) -> None:
    """Register an adapter class so the ConnectionManager can instantiate it by type name."""
    _adapter_classes[adapter_type] = cls
    logger.debug("Adapter class registered", adapter_type=adapter_type, cls=cls.__name__)


class ConnectionManager:
    """Manages the lifecycle of all Bridge adapter connections."""

    def __init__(self):
        self._connections: Dict[str, BridgeAdapter] = {}
        self._tasks: Dict[str, asyncio.Task] = {}
        self._running = False
        self._ssl_context: Optional[ssl.SSLContext] = None

    @property
    def connection_count(self) -> int:
        return len(self._connections)

    async def start(self) -> None:
        """Auto-discover and start adapters based on config."""
        _discover_adapters()
        self._running = True
        settings = get_bridge_settings()

        # Build mTLS context if certs are available
        try:
            self._ssl_context = build_mtls_ssl_context(settings)
            if self._ssl_context:
                logger.info("Bridge mTLS enforcement active")
            elif settings.bridge_trust_enforce:
                logger.error("Bridge mTLS enforcement requested but SSL context could not be built")
                return
        except RuntimeError as e:
            logger.error("Bridge startup blocked by mTLS enforcement", error=str(e))
            raise

        for adapter_type in settings.enabled_adapters:
            conn_id = f"auto-{adapter_type}"
            config = self._build_adapter_config(adapter_type, settings)
            # Inject SSL context so adapters can use mTLS
            if self._ssl_context:
                config["_ssl_context"] = self._ssl_context
            try:
                await self.create_connection(conn_id, adapter_type, config)
                logger.info("Auto-started adapter", adapter_type=adapter_type, connection_id=conn_id)
            except Exception as e:
                logger.error("Failed to auto-start adapter",
                             adapter_type=adapter_type, error=str(e))

    async def stop(self) -> None:
        """Gracefully stop all adapters."""
        self._running = False
        conn_ids = list(self._connections.keys())
        for conn_id in conn_ids:
            await self.remove_connection(conn_id)
        logger.info("ConnectionManager stopped", total_closed=len(conn_ids))

    async def create_connection(
        self, connection_id: str, adapter_type: str, config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create and start a new adapter connection."""
        _discover_adapters()
        if connection_id in self._connections:
            raise ValueError(f"Connection '{connection_id}' already exists")

        cls = _adapter_classes.get(adapter_type)
        if cls is None:
            raise ValueError(
                f"Unknown adapter type '{adapter_type}'. "
                f"Available: {list(_adapter_classes.keys())}"
            )

        adapter = cls(connection_id=connection_id, config=config)
        self._connections[connection_id] = adapter

        # Start adapter in background task
        task = asyncio.create_task(self._run_adapter(adapter))
        self._tasks[connection_id] = task

        return adapter.get_status()

    async def remove_connection(self, connection_id: str) -> bool:
        """Stop and remove an adapter connection."""
        adapter = self._connections.pop(connection_id, None)
        if adapter is None:
            return False

        # Cancel background task
        task = self._tasks.pop(connection_id, None)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        # Disconnect adapter
        try:
            await adapter.disconnect()
        except Exception as e:
            logger.warning("Error disconnecting adapter",
                           connection_id=connection_id, error=str(e))

        logger.info("Connection removed", connection_id=connection_id,
                     adapter_type=adapter.adapter_type)
        return True

    def get_connection(self, connection_id: str) -> Optional[BridgeAdapter]:
        return self._connections.get(connection_id)

    def list_connections(self) -> List[Dict[str, Any]]:
        return [adapter.get_status() for adapter in self._connections.values()]

    async def health(self) -> Dict[str, Any]:
        """Aggregate health from all adapters."""
        adapter_health = {}
        for conn_id, adapter in self._connections.items():
            try:
                adapter_health[conn_id] = await adapter.health()
            except Exception as e:
                adapter_health[conn_id] = {
                    "status": "error",
                    "error": str(e),
                }

        all_ok = all(
            h.get("status") in ("connected", "healthy", "simulated")
            for h in adapter_health.values()
        )

        return {
            "status": "healthy" if all_ok else "degraded",
            "connection_count": self.connection_count,
            "adapters": adapter_health,
        }

    async def send_to(self, connection_id: str, message: Dict[str, Any]) -> bool:
        """Send a message to a specific adapter."""
        adapter = self._connections.get(connection_id)
        if adapter is None:
            logger.warning("Send to unknown connection", connection_id=connection_id)
            return False
        return await adapter.send(message)

    async def broadcast(self, message: Dict[str, Any], adapter_type: Optional[str] = None) -> int:
        """Broadcast a message to all adapters (optionally filtered by type)."""
        sent = 0
        for adapter in self._connections.values():
            if adapter_type and adapter.adapter_type != adapter_type:
                continue
            try:
                if await adapter.send(message):
                    sent += 1
            except Exception as e:
                logger.debug("Broadcast send failed",
                             connection_id=adapter.connection_id, error=str(e))
        return sent

    # ── Internal ─────────────────────────────────────────────────────────────

    async def _run_adapter(self, adapter: BridgeAdapter) -> None:
        """Background task: connect adapter with retry loop."""
        while self._running and adapter.connection_id in self._connections:
            try:
                success = await adapter.connect()
                if success:
                    adapter.status = AdapterStatus.CONNECTED
                    logger.info("Adapter connected",
                                connection_id=adapter.connection_id,
                                adapter_type=adapter.adapter_type)
                    # Block until adapter disconnects or errors
                    while (
                        self._running
                        and adapter.connection_id in self._connections
                        and adapter.status == AdapterStatus.CONNECTED
                    ):
                        await asyncio.sleep(5)
                else:
                    adapter.status = AdapterStatus.RECONNECTING
                    await asyncio.sleep(10)

            except asyncio.CancelledError:
                break
            except Exception as e:
                adapter.set_error(str(e))
                logger.warning("Adapter error, will retry",
                               connection_id=adapter.connection_id, error=str(e))
                adapter.status = AdapterStatus.RECONNECTING
                await asyncio.sleep(10)

    @staticmethod
    def _build_adapter_config(adapter_type: str, settings) -> Dict[str, Any]:
        """Build adapter-specific config dict from BridgeSettings."""
        if adapter_type == "legacy_nac":
            return {
                "legacy_nac_hostname": settings.legacy_nac_hostname,
                "legacy_nac_ers_port": settings.legacy_nac_ers_port,
                "legacy_nac_ers_username": settings.legacy_nac_ers_username,
                "legacy_nac_ers_password": settings.legacy_nac_ers_password,
                "legacy_nac_event_port": settings.legacy_nac_event_port,
                "legacy_nac_node_name": settings.legacy_nac_node_name,
                "legacy_nac_cert_path": settings.legacy_nac_cert_path,
                "legacy_nac_key_path": settings.legacy_nac_key_path,
                "legacy_nac_ca_path": settings.legacy_nac_ca_path,
                "legacy_nac_verify_ssl": settings.legacy_nac_verify_ssl,
                "simulated": settings.simulated,
                "cloud_neuranac_api_url": settings.cloud_neuranac_api_url,
                "cloud_neuranac_ws_url": settings.cloud_neuranac_ws_url,
            }
        elif adapter_type == "neuranac_to_neuranac":
            return {
                "peer_api_url": settings.peer_api_url,
                "peer_grpc_address": settings.peer_grpc_address,
                "nats_url": settings.nats_url,
                "site_id": settings.site_id,
                "tenant_id": settings.tenant_id,
                "deployment_mode": settings.deployment_mode,
                "site_type": settings.site_type,
                "simulated": settings.simulated,
            }
        elif adapter_type == "meraki":
            return {
                "api_key": getattr(settings, "meraki_api_key", ""),
                "organization_id": getattr(settings, "meraki_org_id", ""),
                "simulated": settings.simulated,
            }
        elif adapter_type == "dnac":
            return {
                "host": getattr(settings, "dnac_host", ""),
                "username": getattr(settings, "dnac_username", "admin"),
                "password": getattr(settings, "dnac_password", ""),
                "verify_ssl": getattr(settings, "dnac_verify_ssl", False),
                "simulated": settings.simulated,
            }
        elif adapter_type == "generic_rest":
            return {"simulated": settings.simulated}
        else:
            return {"simulated": settings.simulated}


# ── Singleton ────────────────────────────────────────────────────────────────

_manager: Optional[ConnectionManager] = None


def get_connection_manager() -> ConnectionManager:
    global _manager
    if _manager is None:
        _manager = ConnectionManager()
    return _manager
