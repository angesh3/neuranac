"""Event Stream WebSocket Consumer — connects to Legacy NAC for real-time events.

Supports:
  - STOMP-over-WebSocket protocol (Legacy NAC Event Stream)
  - Auto-reconnect with exponential backoff
  - NATS publish for downstream consumers
  - Simulated mode for development without real Legacy NAC
"""
import asyncio
import json
import os
import time
from datetime import datetime, timezone
from typing import Optional, Dict, Any

import structlog

logger = structlog.get_logger()

EVENT_STREAM_SIMULATED = os.getenv("EVENT_STREAM_SIMULATED", "true").lower() == "true"
EVENT_STREAM_RECONNECT_BASE_DELAY = float(os.getenv("EVENT_STREAM_RECONNECT_DELAY", "5"))
EVENT_STREAM_MAX_RECONNECT_DELAY = float(os.getenv("EVENT_STREAM_MAX_RECONNECT_DELAY", "120"))


class EventStreamConsumerManager:
    """Singleton manager for Event Stream WebSocket consumers per legacy connection."""

    _instance: Optional["EventStreamConsumerManager"] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._consumers: Dict[str, "EventStreamConsumer"] = {}
            cls._instance._lock = asyncio.Lock()
        return cls._instance

    async def connect(self, conn_id: str, config: dict) -> dict:
        """Start or return existing consumer for a connection."""
        async with self._lock:
            if conn_id in self._consumers:
                c = self._consumers[conn_id]
                return {"status": "already_connected", "conn_id": conn_id, "uptime": c.uptime}

            consumer = EventStreamConsumer(conn_id, config)
            self._consumers[conn_id] = consumer
            asyncio.create_task(consumer.run())
            return {"status": "connecting", "conn_id": conn_id}

    async def disconnect(self, conn_id: str) -> dict:
        """Stop consumer for a connection."""
        async with self._lock:
            consumer = self._consumers.pop(conn_id, None)
            if consumer:
                await consumer.stop()
                return {"status": "disconnected", "conn_id": conn_id}
            return {"status": "not_connected", "conn_id": conn_id}

    async def get_status(self, conn_id: str) -> dict:
        """Get status for a specific connection's consumer."""
        async with self._lock:
            consumer = self._consumers.get(conn_id)
            if consumer:
                return consumer.status
            return {"conn_id": conn_id, "connected": False}

    async def get_all_status(self) -> list:
        async with self._lock:
            return [c.status for c in self._consumers.values()]

    async def shutdown(self):
        """Stop all consumers (called on app shutdown)."""
        async with self._lock:
            for conn_id, consumer in list(self._consumers.items()):
                await consumer.stop()
            self._consumers.clear()
            logger.info("Event Stream consumers shut down")


class EventStreamConsumer:
    """Handles a single Event Stream connection with STOMP-over-WebSocket."""

    def __init__(self, conn_id: str, config: dict):
        self.conn_id = conn_id
        self.config = config
        self._running = False
        self._connected = False
        self._started_at: Optional[float] = None
        self._events_received = 0
        self._last_event_at: Optional[str] = None
        self._reconnect_attempts = 0
        # STOMP topics: from config or EVENT_STREAM_STOMP_TOPICS env (comma-separated)
        _env_topics = os.getenv("EVENT_STREAM_STOMP_TOPICS", "").strip()
        env_list = [t.strip() for t in _env_topics.split(",") if t.strip()] if _env_topics else []
        self._topics = config.get("topics", config.get("stomp_topics", env_list or []))

    @property
    def uptime(self) -> str:
        if self._started_at:
            return f"{time.time() - self._started_at:.0f}s"
        return "0s"

    @property
    def status(self) -> dict:
        return {
            "conn_id": self.conn_id,
            "connected": self._connected,
            "running": self._running,
            "uptime": self.uptime,
            "events_received": self._events_received,
            "last_event_at": self._last_event_at,
            "reconnect_attempts": self._reconnect_attempts,
            "simulated": EVENT_STREAM_SIMULATED,
            "topics": self._topics,
        }

    async def run(self):
        """Main loop — connect and process events."""
        self._running = True
        self._started_at = time.time()
        logger.info("Event Stream consumer starting", conn_id=self.conn_id, simulated=EVENT_STREAM_SIMULATED)

        while self._running:
            try:
                if EVENT_STREAM_SIMULATED:
                    await self._run_simulated()
                else:
                    await self._run_real()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self._connected = False
                self._reconnect_attempts += 1
                delay = min(
                    EVENT_STREAM_RECONNECT_BASE_DELAY * (2 ** min(self._reconnect_attempts, 6)),
                    EVENT_STREAM_MAX_RECONNECT_DELAY,
                )
                logger.warning("Event Stream connection error, reconnecting",
                               conn_id=self.conn_id, error=str(e), delay=delay)
                await asyncio.sleep(delay)

        self._connected = False
        self._running = False
        logger.info("Event Stream consumer stopped", conn_id=self.conn_id)

    async def stop(self):
        self._running = False

    async def _run_simulated(self):
        """Generate simulated Event Stream events for development."""
        import random
        self._connected = True
        self._reconnect_attempts = 0
        logger.info("Event Stream simulated mode active", conn_id=self.conn_id)

        event_types = [
            {"topic": "session", "type": "AUTHENTICATION_SUCCESS", "user": "alice@corp.local"},
            {"topic": "session", "type": "AUTHENTICATION_FAILED", "user": "bob@corp.local"},
            {"topic": "session", "type": "ACCOUNTING_START", "user": "charlie@corp.local"},
            {"topic": "radius", "type": "COA_SENT", "user": "device-mac-01"},
            {"topic": "trustsec", "type": "SGT_ASSIGNED", "user": "eve@corp.local"},
        ]

        while self._running:
            await asyncio.sleep(random.uniform(3, 10))
            if not self._running:
                break

            event_template = random.choice(event_types)
            event = {
                "topic": event_template["topic"],
                "type": event_template["type"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": {
                    "username": event_template["user"],
                    "nas_ip": f"10.0.{random.randint(1,10)}.{random.randint(1,254)}",
                    "endpoint_mac": f"AA:BB:CC:{random.randint(10,99)}:{random.randint(10,99)}:{random.randint(10,99)}",
                    "session_id": f"sim-{self.conn_id[:8]}-{random.randint(1000,9999)}",
                },
                "source": "event-stream-simulated",
                "conn_id": self.conn_id,
            }

            self._events_received += 1
            self._last_event_at = event["timestamp"]
            await self._publish_event(event)

    async def _run_real(self):
        """Connect to real Legacy NAC Event Stream via STOMP-over-WebSocket."""
        try:
            import websockets
            import ssl
        except ImportError:
            logger.error("websockets package not installed, falling back to simulated mode")
            await self._run_simulated()
            return

        hostname = self.config.get("hostname", "")
        port = self.config.get("event_stream_port", 8910)
        node_name = self.config.get("event_stream_node_name", "neuranac-consumer")
        cert_path = self.config.get("cert_path", "")
        key_path = self.config.get("key_path", "")
        ca_path = self.config.get("ca_path", "")
        ws_path = self.config.get("event_stream_ws_path", os.getenv("EVENT_STREAM_WS_PATH", "/event-stream/pubsub"))

        ssl_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        if ca_path:
            ssl_ctx.load_verify_locations(ca_path)
        if cert_path and key_path:
            ssl_ctx.load_cert_chain(cert_path, key_path)
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE  # NeuraNAC self-signed certs

        ws_url = f"wss://{hostname}:{port}{ws_path}"
        logger.info("Connecting to Event Stream", url=ws_url, node=node_name)

        async with websockets.connect(ws_url, ssl=ssl_ctx) as ws:
            # STOMP CONNECT
            await ws.send(f"CONNECT\naccept-version:1.2\nhost:{hostname}\n\n\x00")
            frame = await ws.recv()
            if not frame.startswith("CONNECTED"):
                raise ConnectionError(f"STOMP handshake failed: {frame[:100]}")

            self._connected = True
            self._reconnect_attempts = 0
            logger.info("Event Stream STOMP connected", conn_id=self.conn_id)

            # Subscribe to topics
            for i, topic in enumerate(self._topics):
                sub_frame = f"SUBSCRIBE\nid:sub-{i}\ndestination:{topic}\n\n\x00"
                await ws.send(sub_frame)

            # Read events
            while self._running:
                try:
                    raw = await asyncio.wait_for(ws.recv(), timeout=30)
                    if raw.startswith("MESSAGE"):
                        event = self._parse_stomp_message(raw)
                        if event:
                            self._events_received += 1
                            self._last_event_at = datetime.now(timezone.utc).isoformat()
                            await self._publish_event(event)
                    elif raw.startswith("ERROR"):
                        logger.warning("Event Stream STOMP error", frame=raw[:200])
                except asyncio.TimeoutError:
                    # Send heartbeat
                    await ws.send("\n")

    def _parse_stomp_message(self, frame: str) -> Optional[dict]:
        """Parse a STOMP MESSAGE frame into an event dict."""
        try:
            parts = frame.split("\n\n", 1)
            headers_raw = parts[0].split("\n")[1:]  # skip "MESSAGE" line
            headers = {}
            for h in headers_raw:
                if ":" in h:
                    k, v = h.split(":", 1)
                    headers[k.strip()] = v.strip()

            body = parts[1].rstrip("\x00") if len(parts) > 1 else ""
            data = json.loads(body) if body else {}

            return {
                "topic": headers.get("destination", "unknown"),
                "type": data.get("type", "UNKNOWN"),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": data,
                "source": "event-stream",
                "conn_id": self.conn_id,
            }
        except Exception as e:
            logger.warning("Failed to parse STOMP message", error=str(e))
            return None

    async def _publish_event(self, event: dict):
        """Publish event to NATS and in-process EventBus."""
        # NATS publish
        try:
            from app.services.nats_client import get_nats_js
            js = get_nats_js()
            if js:
                topic = f"event_stream.events.{event.get('topic', 'unknown')}"
                await js.publish(topic, json.dumps(event).encode())
        except Exception:
            pass  # NATS unavailable — degrade gracefully

        # In-process EventBus for WebSocket push
        try:
            from app.routers.websocket_events import event_bus
            await event_bus.publish("event-stream", event)
        except Exception:
            pass
