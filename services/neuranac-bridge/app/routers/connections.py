"""Connections Router — CRUD for Bridge adapter connections.

Allows runtime management of adapter connections:
  - List all connections
  - Create a new connection (spawns adapter)
  - Get connection details
  - Delete a connection (stops adapter)
  - Send a message to a specific connection
"""
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.connection_manager import get_connection_manager

router = APIRouter()


class ConnectionCreate(BaseModel):
    connection_id: str
    adapter_type: str  # "legacy_nac", "neuranac_to_neuranac", "generic_rest"
    config: dict = {}


class ConnectionMessage(BaseModel):
    type: str
    method: Optional[str] = None
    path: Optional[str] = None
    body: Optional[str] = None
    headers: Optional[dict] = None
    data: Optional[dict] = None


@router.get("/")
async def list_connections():
    """List all active adapter connections."""
    manager = get_connection_manager()
    return {"items": manager.list_connections(), "total": manager.connection_count}


@router.post("/", status_code=201)
async def create_connection(body: ConnectionCreate):
    """Create and start a new adapter connection."""
    manager = get_connection_manager()
    try:
        result = await manager.create_connection(
            connection_id=body.connection_id,
            adapter_type=body.adapter_type,
            config=body.config,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{connection_id}")
async def get_connection(connection_id: str):
    """Get details for a specific connection."""
    manager = get_connection_manager()
    adapter = manager.get_connection(connection_id)
    if adapter is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    return await adapter.health()


@router.delete("/{connection_id}")
async def delete_connection(connection_id: str):
    """Stop and remove a connection."""
    manager = get_connection_manager()
    removed = await manager.remove_connection(connection_id)
    if not removed:
        raise HTTPException(status_code=404, detail="Connection not found")
    return {"connection_id": connection_id, "status": "removed"}


@router.post("/{connection_id}/send")
async def send_to_connection(connection_id: str, body: ConnectionMessage):
    """Send a message to a specific adapter connection."""
    manager = get_connection_manager()
    adapter = manager.get_connection(connection_id)
    if adapter is None:
        raise HTTPException(status_code=404, detail="Connection not found")

    message = body.model_dump(exclude_none=True)
    success = await adapter.send(message)
    return {"connection_id": connection_id, "sent": success}
