"""Bridge Adapter Base — abstract interface for all connection adapters.

Every adapter (NeuraNAC, NeuraNAC-to-NeuraNAC, Meraki, Generic REST, etc.) implements this
interface. The ConnectionManager discovers, spawns, and lifecycle-manages
adapters through these methods.

Usage:
    class MyAdapter(BridgeAdapter):
        adapter_type = "my_adapter"
        async def connect(self): ...
        async def disconnect(self): ...
        async def health(self) -> dict: ...
        async def send(self, message: dict): ...
        async def on_message(self, message: dict): ...
"""
from __future__ import annotations

import abc
from enum import Enum
from typing import Any, Dict, Optional


class AdapterStatus(str, Enum):
    INITIALIZING = "initializing"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    RECONNECTING = "reconnecting"
    ERROR = "error"
    DRAINING = "draining"


class BridgeAdapter(abc.ABC):
    """Abstract base class for all NeuraNAC Bridge adapters."""

    adapter_type: str = "base"

    def __init__(self, connection_id: str, config: Dict[str, Any]):
        self.connection_id = connection_id
        self.config = config
        self.status = AdapterStatus.INITIALIZING
        self._error: Optional[str] = None

    @abc.abstractmethod
    async def connect(self) -> bool:
        """Establish the adapter connection. Returns True on success."""
        ...

    @abc.abstractmethod
    async def disconnect(self) -> None:
        """Gracefully close the adapter connection."""
        ...

    @abc.abstractmethod
    async def health(self) -> Dict[str, Any]:
        """Return health/status information for this adapter."""
        ...

    @abc.abstractmethod
    async def send(self, message: Dict[str, Any]) -> bool:
        """Send a message through this adapter. Returns True on success."""
        ...

    async def on_message(self, message: Dict[str, Any]) -> None:
        """Handle an inbound message received by this adapter.

        Override in subclasses that support bidirectional messaging.
        Default implementation is a no-op.
        """
        pass

    def get_status(self) -> Dict[str, Any]:
        """Return a summary dict of this adapter's state."""
        return {
            "connection_id": self.connection_id,
            "adapter_type": self.adapter_type,
            "status": self.status.value,
            "error": self._error,
        }

    def set_error(self, error: str) -> None:
        self.status = AdapterStatus.ERROR
        self._error = error

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} id={self.connection_id} status={self.status.value}>"
