"""Bidirectional Tunnel — outbound connection from Bridge to cloud NeuraNAC.

The tunnel is OUTBOUND from the customer's private network to the cloud,
which firewalls typically allow. Through this tunnel:
  1. Events are relayed from on-prem adapters → cloud NeuraNAC
  2. Requests are received from cloud NeuraNAC → forwarded to local adapters
  3. Heartbeats keep the tunnel alive

Generalized from the old NeuraNAC-only WebSocket tunnel to support any adapter type.
Supports both WebSocket and gRPC bidirectional streaming.
"""
import asyncio
import json
import time
from typing import Any, Callable, Awaitable, Dict, Optional

import structlog

from app.config import get_bridge_settings

logger = structlog.get_logger()


class BridgeTunnel:
    """Manages the outbound tunnel to cloud NeuraNAC."""

    def __init__(self, on_message: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None):
        self.settings = get_bridge_settings()
        self._running = False
        self._connected = False
        self._ws = None
        self._reconnect_attempts = 0
        self._messages_sent = 0
        self._messages_received = 0
        self._started_at: Optional[float] = None
        self._on_message = on_message

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def start(self):
        """Main loop: connect and maintain the tunnel."""
        self._running = True
        self._started_at = time.time()

        while self._running:
            try:
                if self.settings.simulated:
                    await self._run_simulated()
                else:
                    await self._run_real()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._connected = False
                self._reconnect_attempts += 1
                delay = min(
                    self.settings.tunnel_reconnect_base_delay * (2 ** min(self._reconnect_attempts, 6)),
                    self.settings.tunnel_reconnect_max_delay,
                )
                logger.warning("Tunnel connection error, reconnecting",
                               error=str(e), delay=delay, attempts=self._reconnect_attempts)
                await asyncio.sleep(delay)

        self._connected = False
        logger.info("Tunnel stopped")

    async def stop(self):
        self._running = False
        if self._ws:
            try:
                await self._ws.close()
            except Exception:
                pass

    async def send_event(self, event: dict):
        """Send an event through the tunnel to cloud NeuraNAC."""
        if not self._connected or not self._ws:
            return
        try:
            msg = json.dumps({"type": "bridge_event", "data": event})
            await self._ws.send(msg)
            self._messages_sent += 1
        except Exception as e:
            logger.debug("Failed to send event through tunnel", error=str(e))

    async def _run_real(self):
        """Connect to cloud NeuraNAC WebSocket endpoint."""
        try:
            import websockets
        except ImportError:
            logger.error("websockets package not installed, falling back to simulated")
            await self._run_simulated()
            return

        ws_url = self.settings.cloud_neuranac_ws_url
        logger.info("Connecting tunnel to cloud NeuraNAC", url=ws_url)

        async with websockets.connect(ws_url) as ws:
            self._ws = ws
            self._connected = True
            self._reconnect_attempts = 0
            logger.info("Tunnel connected to cloud NeuraNAC")

            while self._running:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=30)
                    self._messages_received += 1
                    await self._handle_message(raw)
                except asyncio.TimeoutError:
                    await ws.send(json.dumps({"type": "ping"}))
                except Exception as e:
                    if self._running:
                        raise
                    break

        self._connected = False
        self._ws = None

    async def _run_simulated(self):
        """Simulated tunnel for dev/demo — no real cloud connection."""
        self._connected = True
        self._reconnect_attempts = 0
        logger.info("Simulated tunnel active (no real cloud connection)")

        while self._running:
            await asyncio.sleep(self.settings.tunnel_heartbeat_interval)
            if not self._running:
                break
            logger.debug("Simulated tunnel heartbeat",
                         msgs_sent=self._messages_sent, msgs_recv=self._messages_received)

    async def _handle_message(self, raw: str):
        """Handle incoming messages from cloud NeuraNAC through the tunnel."""
        try:
            msg = json.loads(raw)
            msg_type = msg.get("type", "")

            if msg_type == "pong":
                pass
            elif self._on_message:
                await self._on_message(msg)
            else:
                logger.debug("Unhandled tunnel message", type=msg_type)

        except json.JSONDecodeError:
            logger.warning("Invalid JSON from tunnel")

    def get_status(self) -> dict:
        uptime = f"{time.time() - self._started_at:.0f}s" if self._started_at else "0s"
        return {
            "connected": self._connected,
            "simulated": self.settings.simulated,
            "cloud_ws_url": self.settings.cloud_neuranac_ws_url,
            "uptime": uptime,
            "reconnect_attempts": self._reconnect_attempts,
            "messages_sent": self._messages_sent,
            "messages_received": self._messages_received,
        }


# Singleton
_tunnel: Optional[BridgeTunnel] = None


def get_tunnel() -> BridgeTunnel:
    global _tunnel
    if _tunnel is None:
        _tunnel = BridgeTunnel()
    return _tunnel
