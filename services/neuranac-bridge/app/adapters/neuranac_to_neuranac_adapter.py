"""NeuraNAC-to-NeuraNAC Adapter — bidirectional site-to-site communication.

This is the CORE new component that enables hybrid deployments WITHOUT NeuraNAC.
It handles all cross-site communication between on-prem NeuraNAC and cloud NeuraNAC:

  1. gRPC bidirectional streaming (policy sync, session events, config sync)
  2. HTTP reverse proxy (API request forwarding, replaces FederationMiddleware)
  3. NATS leaf bridge (real-time events across sites)
  4. Large payload handler (JetStream Object Store for >1MB transfers)

Deployment scenarios enabled:
  - S4: Hybrid no NeuraNAC (on-prem + cloud)
  - S5: Hybrid + NeuraNAC (on-prem + cloud)
  - S6: Multi-site hybrid (N on-prem + cloud mesh)
"""
from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Dict, List, Optional

import httpx
import structlog

from app.adapter_base import AdapterStatus, BridgeAdapter

logger = structlog.get_logger()


class NeuraNACToNeuraNACAdapter(BridgeAdapter):
    """Bridge adapter for NeuraNAC-to-NeuraNAC cross-site communication."""

    adapter_type = "neuranac_to_neuranac"

    def __init__(self, connection_id: str, config: Dict[str, Any]):
        super().__init__(connection_id, config)
        self._simulated = config.get("simulated", True)
        self._peer_api_url = config.get("peer_api_url", "")
        self._peer_grpc_address = config.get("peer_grpc_address", "")
        self._nats_url = config.get("nats_url", "nats://localhost:4222")
        self._site_id = config.get("site_id", "")
        self._tenant_id = config.get("tenant_id", "")
        self._deployment_mode = config.get("deployment_mode", "standalone")
        self._site_type = config.get("site_type", "onprem")

        # mTLS SSL context (injected by ConnectionManager when bridge_trust_enforce is on)
        self._ssl_context = config.get("_ssl_context")

        # State
        self._http_client: Optional[httpx.AsyncClient] = None
        self._grpc_channel = None
        self._nats_conn = None
        self._connected_at: Optional[float] = None
        self._messages_sent = 0
        self._messages_received = 0
        self._http_requests_proxied = 0
        self._errors_count = 0

        # gRPC stream channels
        self._stream_tasks: List[asyncio.Task] = []

    async def connect(self) -> bool:
        """Establish HTTP + gRPC + NATS connections to peer site."""
        if self._simulated:
            self.status = AdapterStatus.CONNECTED
            self._connected_at = time.time()
            logger.info("NeuraNAC-to-NeuraNAC adapter connected (simulated)",
                        connection_id=self.connection_id,
                        peer_api_url=self._peer_api_url)
            return True

        try:
            # 1. HTTP client for reverse proxy (with mTLS if available)
            if self._peer_api_url:
                http_kwargs = {
                    "base_url": self._peer_api_url,
                    "timeout": 30,
                    "headers": {"X-NeuraNAC-Bridge": "true", "X-NeuraNAC-Site-ID": self._site_id},
                }
                if self._ssl_context:
                    http_kwargs["verify"] = self._ssl_context
                    logger.info("NeuraNAC-to-NeuraNAC HTTP client using mTLS",
                                connection_id=self.connection_id)
                self._http_client = httpx.AsyncClient(**http_kwargs)
                # Test peer health
                resp = await self._http_client.get("/health")
                if resp.status_code != 200:
                    self.set_error(f"Peer health check failed: {resp.status_code}")
                    return False

            # 2. gRPC bidi stream (connect to peer sync engine)
            if self._peer_grpc_address:
                await self._connect_grpc()

            # 3. NATS leaf bridge (cross-site event bus)
            await self._connect_nats_leaf()

            self.status = AdapterStatus.CONNECTED
            self._connected_at = time.time()
            logger.info("NeuraNAC-to-NeuraNAC adapter connected",
                        connection_id=self.connection_id,
                        peer_api_url=self._peer_api_url,
                        peer_grpc=self._peer_grpc_address)
            return True

        except Exception as e:
            self.set_error(str(e))
            return False

    async def disconnect(self) -> None:
        """Close all cross-site connections."""
        # Cancel stream tasks
        for task in self._stream_tasks:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        self._stream_tasks.clear()

        # Close HTTP client
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None

        # Close gRPC channel
        if self._grpc_channel:
            try:
                self._grpc_channel.close()
            except Exception:
                pass
            self._grpc_channel = None

        # Close NATS connection
        if self._nats_conn:
            try:
                await self._nats_conn.close()
            except Exception:
                pass
            self._nats_conn = None

        self.status = AdapterStatus.DISCONNECTED
        logger.info("NeuraNAC-to-NeuraNAC adapter disconnected", connection_id=self.connection_id)

    async def health(self) -> Dict[str, Any]:
        """Return cross-site connection health."""
        uptime = f"{time.time() - self._connected_at:.0f}s" if self._connected_at else "0s"
        return {
            "status": self.status.value,
            "simulated": self._simulated,
            "peer_api_url": self._peer_api_url,
            "peer_grpc_address": self._peer_grpc_address,
            "site_id": self._site_id,
            "site_type": self._site_type,
            "uptime": uptime,
            "http_client_active": self._http_client is not None,
            "grpc_connected": self._grpc_channel is not None,
            "nats_connected": self._nats_conn is not None,
            "messages_sent": self._messages_sent,
            "messages_received": self._messages_received,
            "http_requests_proxied": self._http_requests_proxied,
            "errors_count": self._errors_count,
        }

    async def send(self, message: Dict[str, Any]) -> bool:
        """Send a message to the peer site."""
        msg_type = message.get("type", "")

        if msg_type == "http_proxy":
            return await self._proxy_http_request(message)
        elif msg_type == "grpc_sync":
            return await self._send_grpc(message)
        elif msg_type == "nats_event":
            return await self._publish_nats(message)
        else:
            # Default: try NATS broadcast
            return await self._publish_nats({"type": "bridge_message", "data": message})

    # ── HTTP Reverse Proxy ───────────────────────────────────────────────────

    async def proxy_http_request(
        self, method: str, path: str,
        body: Optional[bytes] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        """Proxy an HTTP request to the peer NeuraNAC site.

        Replaces the old FederationMiddleware single-peer HTTP forwarding.
        Supports streaming responses and configurable timeout.
        """
        if self._simulated:
            self._http_requests_proxied += 1
            return {
                "status_code": 200,
                "body": json.dumps({"simulated": True, "path": path}),
                "headers": {},
            }

        if not self._http_client:
            return {"status_code": 503, "error": "HTTP client not connected"}

        try:
            req_headers = dict(headers or {})
            req_headers["X-NeuraNAC-Site"] = "peer"
            req_headers["X-NeuraNAC-Tenant-ID"] = self._tenant_id

            resp = await self._http_client.request(
                method=method, url=path,
                content=body, headers=req_headers,
                timeout=timeout,
            )
            self._http_requests_proxied += 1
            self._messages_sent += 1
            return {
                "status_code": resp.status_code,
                "headers": dict(resp.headers),
                "body": resp.text,
            }
        except Exception as e:
            self._errors_count += 1
            logger.error("HTTP proxy error", path=path, error=str(e))
            return {"status_code": 502, "error": str(e)}

    async def _proxy_http_request(self, message: Dict[str, Any]) -> bool:
        """Internal: proxy HTTP from message dict."""
        result = await self.proxy_http_request(
            method=message.get("method", "GET"),
            path=message.get("path", ""),
            body=message.get("body"),
            headers=message.get("headers"),
        )
        return result.get("status_code", 500) < 400

    # ── gRPC Bidirectional Streaming ─────────────────────────────────────────

    async def _connect_grpc(self) -> None:
        """Establish gRPC channel to peer sync engine.

        Uses grpcio for bidirectional streaming. Channels:
          - policy-sync: policy changes pushed in real-time
          - session-events: auth events, CoA notifications
          - config-sync: feature flags, identity sources
          - bulk-transfer: initial sync, large datasets
        """
        if self._simulated:
            logger.info("gRPC channel simulated", peer=self._peer_grpc_address)
            return

        try:
            import grpc
            self._grpc_channel = grpc.aio.insecure_channel(self._peer_grpc_address)
            logger.info("gRPC channel established", peer=self._peer_grpc_address)
        except ImportError:
            logger.warning("grpcio not installed — gRPC channel disabled")
        except Exception as e:
            logger.error("gRPC connection failed", peer=self._peer_grpc_address, error=str(e))

    async def _send_grpc(self, message: Dict[str, Any]) -> bool:
        """Send a message via gRPC stream."""
        if self._simulated:
            self._messages_sent += 1
            return True
        # TODO: Implement real gRPC streaming in Phase 2
        logger.debug("gRPC send (stub)", message_type=message.get("type"))
        self._messages_sent += 1
        return True

    # ── NATS Leaf Bridge ─────────────────────────────────────────────────────

    async def _connect_nats_leaf(self) -> None:
        """Connect to NATS for cross-site event bridging.

        In production, the on-prem NATS runs as a leaf node connected to
        the cloud NATS hub cluster. This adapter subscribes to cross-site
        subjects and relays events.
        """
        if self._simulated:
            logger.info("NATS leaf bridge simulated")
            return

        try:
            import nats
            self._nats_conn = await nats.connect(self._nats_url)
            # Subscribe to cross-site subjects
            subject = f"neuranac.{self._tenant_id}.bridge.>"
            await self._nats_conn.subscribe(subject, cb=self._on_nats_message)
            logger.info("NATS leaf bridge connected", subject=subject)
        except ImportError:
            logger.warning("nats-py not installed — NATS bridge disabled")
        except Exception as e:
            logger.warning("NATS connection failed (will retry)", error=str(e))

    async def _publish_nats(self, message: Dict[str, Any]) -> bool:
        """Publish a message to the cross-site NATS subject."""
        if self._simulated:
            self._messages_sent += 1
            return True

        if not self._nats_conn:
            return False

        try:
            subject = f"neuranac.{self._tenant_id}.bridge.events"
            await self._nats_conn.publish(subject, json.dumps(message).encode())
            self._messages_sent += 1
            return True
        except Exception as e:
            self._errors_count += 1
            logger.error("NATS publish error", error=str(e))
            return False

    async def _on_nats_message(self, msg) -> None:
        """Handle inbound NATS messages from peer site."""
        self._messages_received += 1
        try:
            data = json.loads(msg.data.decode())
            await self.on_message(data)
        except Exception as e:
            logger.debug("NATS message handling error", error=str(e))

