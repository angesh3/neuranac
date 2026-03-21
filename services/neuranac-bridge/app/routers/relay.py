"""Relay Router — receives proxied requests from cloud API Gateway,
forwards them through the appropriate adapter.

Supports both NeuraNAC ERS relay (backward compatible) and generic adapter relay.
"""
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import structlog

from app.connection_manager import get_connection_manager

logger = structlog.get_logger()
router = APIRouter()


class RelayRequest(BaseModel):
    method: str = "GET"
    path: str
    body: Optional[str] = None
    headers: Optional[dict] = None


@router.post("/ers")
async def relay_ers_request(req: RelayRequest):
    """Proxy an ERS API request to the local NeuraNAC instance via the NeuraNAC adapter.

    Backward-compatible with the old Bridge Connector relay endpoint.
    """
    manager = get_connection_manager()

    # Find an NeuraNAC adapter
    for conn in manager.list_connections():
        if conn.get("adapter_type") == "legacy_nac":
            adapter = manager.get_connection(conn["connection_id"])
            if adapter and hasattr(adapter, "proxy_ers_request"):
                body_bytes = req.body.encode() if req.body else None
                result = await adapter.proxy_ers_request(
                    method=req.method,
                    path=req.path,
                    body=body_bytes,
                    headers=req.headers,
                )
                return result

    raise HTTPException(status_code=503, detail="No NeuraNAC adapter connected")


@router.get("/ers/test")
async def test_ers_relay():
    """Quick test: proxy a version check to NeuraNAC ERS API."""
    manager = get_connection_manager()
    for conn in manager.list_connections():
        if conn.get("adapter_type") == "legacy_nac":
            adapter = manager.get_connection(conn["connection_id"])
            if adapter and hasattr(adapter, "test_connection"):
                result = await adapter.test_connection()
                return {"relay_status": "ok", "lnac_response": result}

    raise HTTPException(status_code=503, detail="No NeuraNAC adapter connected")


@router.post("/proxy")
async def relay_http_proxy(req: RelayRequest):
    """Proxy an HTTP request to the peer NeuraNAC site via the NeuraNAC-to-NeuraNAC adapter."""
    manager = get_connection_manager()
    for conn in manager.list_connections():
        if conn.get("adapter_type") == "neuranac_to_neuranac":
            adapter = manager.get_connection(conn["connection_id"])
            if adapter and hasattr(adapter, "proxy_http_request"):
                result = await adapter.proxy_http_request(
                    method=req.method,
                    path=req.path,
                    body=req.body.encode() if req.body else None,
                    headers=req.headers,
                )
                return result

    raise HTTPException(status_code=503, detail="No NeuraNAC-to-NeuraNAC adapter connected")


@router.get("/event-stream/status")
async def event_stream_relay_status():
    """Get Event Stream relay status from the NeuraNAC adapter."""
    manager = get_connection_manager()
    for conn in manager.list_connections():
        if conn.get("adapter_type") == "legacy_nac":
            adapter = manager.get_connection(conn["connection_id"])
            if adapter:
                h = await adapter.health()
                return {
                    "event_stream_connected": h.get("event_stream_connected", False),
                    "event_stream_events_count": h.get("event_stream_events_count", 0),
                    "legacy_nac_hostname": h.get("legacy_nac_hostname", ""),
                    "simulated": h.get("simulated", True),
                }

    return {"event_stream_connected": False, "event_stream_events_count": 0,
            "legacy_nac_hostname": "", "simulated": True}
