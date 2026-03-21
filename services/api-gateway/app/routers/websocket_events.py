"""WebSocket events endpoint — real-time browser push for Event Stream, sessions, CoA events.

Supports in-band token refresh: clients send {"action": "refresh_token", "token": "NEW_JWT"}
to extend long-lived connections without reconnecting.
"""
import asyncio
import json
import os
import time
from collections import defaultdict
from typing import Dict, Optional, Set

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from jose import JWTError
import structlog

from app.middleware.auth import decode_token

logger = structlog.get_logger()

# How often (seconds) the server checks whether a client's token has expired
WS_TOKEN_CHECK_INTERVAL = int(os.getenv("WS_TOKEN_CHECK_INTERVAL", "60"))
# Grace period (seconds) after token expiry before forcibly closing the connection
WS_TOKEN_EXPIRY_GRACE = int(os.getenv("WS_TOKEN_EXPIRY_GRACE", "300"))

router = APIRouter()

# ── Rate limiting config ─────────────────────────────────────────────────────
WS_MAX_CONNECTIONS_PER_IP = int(os.getenv("WS_MAX_CONNECTIONS_PER_IP", "10"))
WS_MAX_MESSAGES_PER_MINUTE = int(os.getenv("WS_MAX_MESSAGES_PER_MINUTE", "60"))
WS_MAX_TOTAL_CONNECTIONS = int(os.getenv("WS_MAX_TOTAL_CONNECTIONS", "500"))


class WSRateLimiter:
    """Per-IP connection tracking and per-connection message rate limiting."""

    def __init__(self):
        self._ip_counts: Dict[str, int] = defaultdict(int)
        self._msg_windows: Dict[int, list] = {}  # ws id -> list of timestamps
        self._lock = asyncio.Lock()

    async def allow_connect(self, ip: str, total: int) -> tuple:
        """Return (allowed: bool, reason: str)."""
        async with self._lock:
            if total >= WS_MAX_TOTAL_CONNECTIONS:
                return False, f"Server at max connections ({WS_MAX_TOTAL_CONNECTIONS})"
            if self._ip_counts[ip] >= WS_MAX_CONNECTIONS_PER_IP:
                return False, f"Too many connections from {ip} (max {WS_MAX_CONNECTIONS_PER_IP})"
            self._ip_counts[ip] += 1
            return True, ""

    async def on_disconnect(self, ip: str, ws_id: int):
        async with self._lock:
            self._ip_counts[ip] = max(0, self._ip_counts[ip] - 1)
            if self._ip_counts[ip] == 0:
                self._ip_counts.pop(ip, None)
            self._msg_windows.pop(ws_id, None)

    async def allow_message(self, ws_id: int) -> bool:
        """Sliding-window rate limit on inbound messages."""
        now = time.monotonic()
        async with self._lock:
            window = self._msg_windows.setdefault(ws_id, [])
            cutoff = now - 60
            self._msg_windows[ws_id] = [t for t in window if t > cutoff]
            if len(self._msg_windows[ws_id]) >= WS_MAX_MESSAGES_PER_MINUTE:
                return False
            self._msg_windows[ws_id].append(now)
            return True

    @property
    def stats(self) -> dict:
        return {
            "ips_tracked": len(self._ip_counts),
            "total_ip_connections": sum(self._ip_counts.values()),
            "config": {
                "max_per_ip": WS_MAX_CONNECTIONS_PER_IP,
                "max_messages_per_min": WS_MAX_MESSAGES_PER_MINUTE,
                "max_total": WS_MAX_TOTAL_CONNECTIONS,
            },
        }


rate_limiter = WSRateLimiter()


class ConnectionManager:
    """Manages active WebSocket connections grouped by topic."""

    def __init__(self):
        self.connections: Dict[str, Set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket, topics: list[str]):
        await ws.accept()
        async with self._lock:
            for topic in topics:
                if topic not in self.connections:
                    self.connections[topic] = set()
                self.connections[topic].add(ws)
        logger.info("WebSocket connected", topics=topics)

    async def disconnect(self, ws: WebSocket):
        async with self._lock:
            for topic in list(self.connections.keys()):
                self.connections[topic].discard(ws)
                if not self.connections[topic]:
                    del self.connections[topic]

    async def broadcast(self, topic: str, message: dict):
        async with self._lock:
            sockets = list(self.connections.get(topic, set()))
        dead = []
        for ws in sockets:
            try:
                await ws.send_json(message)
            except Exception:
                dead.append(ws)
        for ws in dead:
            await self.disconnect(ws)

    @property
    def active_count(self) -> int:
        return sum(len(s) for s in self.connections.values())


manager = ConnectionManager()


class EventBus:
    """In-process event bus fallback when NATS is unavailable."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._subscribers = []
        return cls._instance

    def subscribe(self, callback):
        self._subscribers.append(callback)

    def unsubscribe(self, callback):
        self._subscribers = [s for s in self._subscribers if s is not callback]

    async def publish(self, topic: str, data: dict):
        for cb in self._subscribers:
            try:
                await cb(topic, data)
            except Exception as e:
                logger.warning("EventBus callback error", error=str(e))


event_bus = EventBus()


async def _on_event(topic: str, data: dict):
    """Forward EventBus messages to WebSocket clients."""
    await manager.broadcast(topic, {"topic": topic, "data": data})

event_bus.subscribe(_on_event)


@router.websocket("/events")
async def websocket_events(
    ws: WebSocket,
    topics: str = Query(default="sessions,event-stream,coa"),
    token: str = Query(default=""),
):
    """
    WebSocket endpoint for real-time event streaming.

    Connect: ws://HOST:8080/api/v1/ws/events?topics=sessions,event-stream,coa&token=JWT

    In-band token refresh (no reconnect needed):
        Send: {"action": "refresh_token", "token": "NEW_ACCESS_JWT"}
        Recv: {"type": "token_refreshed", "expires_in": <seconds>}
    """
    # Authenticate via token query param (WebSocket can't use Authorization header)
    if not token:
        await ws.close(code=4001, reason="Authentication required: provide ?token=JWT")
        return
    try:
        payload = decode_token(token)
        if payload.get("type") == "refresh":
            await ws.close(code=4001, reason="Access token required, not refresh token")
            return
    except Exception:
        await ws.close(code=4001, reason="Invalid or expired token")
        return

    topic_list = [t.strip() for t in topics.split(",") if t.strip()]
    if not topic_list:
        topic_list = ["sessions"]

    # Rate limit: per-IP connection count
    client_ip = ws.client.host if ws.client else "unknown"
    allowed, reason = await rate_limiter.allow_connect(client_ip, manager.active_count)
    if not allowed:
        await ws.accept()
        await ws.close(code=4029, reason=reason)
        logger.warning("WebSocket rate limited", ip=client_ip, reason=reason)
        return

    ws_id = id(ws)
    await manager.connect(ws, topic_list)

    # Token state for this connection
    token_exp: Optional[float] = payload.get("exp")
    token_warned = False

    async def _token_expiry_monitor():
        """Background task: warn client and close connection on token expiry."""
        nonlocal token_exp, token_warned
        while True:
            await asyncio.sleep(WS_TOKEN_CHECK_INTERVAL)
            if token_exp is None:
                continue
            now = time.time()
            remaining = token_exp - now
            if remaining <= 0:
                if remaining < -WS_TOKEN_EXPIRY_GRACE:
                    # Grace period exhausted — close connection
                    try:
                        await ws.send_json({
                            "type": "token_expired",
                            "message": "Token expired and grace period exhausted. Closing connection.",
                        })
                        await ws.close(code=4001, reason="Token expired")
                    except Exception:
                        pass
                    return
                elif not token_warned:
                    try:
                        await ws.send_json({
                            "type": "token_expiring",
                            "message": "Token has expired. Send {\"action\": \"refresh_token\", \"token\": \"NEW_JWT\"} to stay connected.",
                            "grace_seconds": WS_TOKEN_EXPIRY_GRACE,
                        })
                    except Exception:
                        pass
                    token_warned = True
            elif remaining < 120 and not token_warned:
                # Warn 2 minutes before expiry
                try:
                    await ws.send_json({
                        "type": "token_expiring",
                        "message": f"Token expires in {int(remaining)}s. Send a refresh_token to stay connected.",
                        "expires_in": int(remaining),
                    })
                except Exception:
                    pass
                token_warned = True

    # Start background token monitor
    monitor_task = asyncio.create_task(_token_expiry_monitor())

    try:
        # Send initial confirmation
        expires_in = int(token_exp - time.time()) if token_exp else None
        await ws.send_json({
            "type": "connected",
            "topics": topic_list,
            "message": "Subscribed to real-time events",
            "token_expires_in": expires_in,
        })
        # Keep connection alive — read client pings/messages
        while True:
            data = await ws.receive_text()

            # Rate limit: per-connection message rate
            if not await rate_limiter.allow_message(ws_id):
                await ws.send_json({"type": "error", "message": "Rate limit exceeded"})
                continue

            # Handle client-side ping
            if data == "ping":
                await ws.send_json({"type": "pong"})
                continue

            # Handle structured messages
            try:
                msg = json.loads(data)
            except (json.JSONDecodeError, TypeError):
                continue

            action = msg.get("action")

            # ── In-band token refresh ──────────────────────────────────
            if action == "refresh_token":
                new_token = msg.get("token", "")
                if not new_token:
                    await ws.send_json({"type": "error", "message": "Missing 'token' field"})
                    continue
                try:
                    new_payload = decode_token(new_token)
                    if new_payload.get("type") == "refresh":
                        await ws.send_json({"type": "error", "message": "Access token required, not refresh token"})
                        continue
                    token_exp = new_payload.get("exp")
                    token_warned = False
                    new_expires_in = int(token_exp - time.time()) if token_exp else None
                    await ws.send_json({
                        "type": "token_refreshed",
                        "expires_in": new_expires_in,
                        "message": "Token refreshed successfully",
                    })
                    logger.debug("WebSocket token refreshed", ws_id=ws_id,
                                 expires_in=new_expires_in)
                except Exception:
                    await ws.send_json({"type": "error", "message": "Invalid or expired refresh token"})
                continue

            # ── Topic subscription changes ─────────────────────────────
            if action == "subscribe":
                new_topics = msg.get("topics", [])
                await manager.connect(ws, new_topics)
                await ws.send_json({"type": "subscribed", "topics": new_topics})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.warning("WebSocket error", error=str(e))
    finally:
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass
        await manager.disconnect(ws)
        await rate_limiter.on_disconnect(client_ip, ws_id)


@router.get("/events/status")
async def ws_status():
    """Get WebSocket connection status."""
    return {
        "active_connections": manager.active_count,
        "topics": list(manager.connections.keys()),
        "rate_limiter": rate_limiter.stats,
    }
