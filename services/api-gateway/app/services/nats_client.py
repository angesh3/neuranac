"""NATS JetStream client for the API Gateway.

Provides publish capability for event-driven features like incremental
policy reload, session events, and CoA requests.
"""
from typing import Optional

import structlog

logger = structlog.get_logger()

_nc = None  # nats.Client
_js = None  # nats.js.JetStreamContext


async def init_nats():
    """Connect to NATS and obtain a JetStream context."""
    global _nc, _js
    try:
        import nats as nats_pkg
        from app.config import get_settings
        settings = get_settings()
        _nc = await nats_pkg.connect(settings.nats_url)
        _js = _nc.jetstream()
        logger.info("NATS JetStream connected", url=settings.nats_url)
    except Exception as exc:
        _nc = None
        _js = None
        logger.warning("NATS unavailable — event publishing disabled", error=str(exc))


async def close_nats():
    global _nc, _js
    _js = None
    if _nc is not None:
        try:
            await _nc.close()
            logger.info("NATS connection closed")
        except Exception as exc:
            logger.warning("Error closing NATS connection", error=str(exc))
        _nc = None


def get_nats_js() -> Optional[object]:
    """Return the JetStream context, or None when unavailable."""
    return _js
