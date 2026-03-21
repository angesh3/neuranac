"""Tests for ConnectionManager — adapter lifecycle, CRUD, health aggregation."""
import pytest
import asyncio
from unittest.mock import patch, AsyncMock

from app.adapter_base import AdapterStatus, BridgeAdapter
from app.connection_manager import ConnectionManager, register_adapter_class, _adapter_classes


class MockAdapter(BridgeAdapter):
    adapter_type = "mock"

    async def connect(self) -> bool:
        self.status = AdapterStatus.CONNECTED
        return True

    async def disconnect(self) -> None:
        self.status = AdapterStatus.DISCONNECTED

    async def health(self) -> dict:
        return {"status": self.status.value, "simulated": True}

    async def send(self, message: dict) -> bool:
        return True


class FailingMockAdapter(BridgeAdapter):
    adapter_type = "mock_fail"

    async def connect(self) -> bool:
        self.set_error("always fails")
        return False

    async def disconnect(self) -> None:
        self.status = AdapterStatus.DISCONNECTED

    async def health(self) -> dict:
        return {"status": self.status.value, "error": self._error}

    async def send(self, message: dict) -> bool:
        return False


@pytest.fixture(autouse=True)
def register_mocks():
    """Register mock adapters for testing."""
    register_adapter_class("mock", MockAdapter)
    register_adapter_class("mock_fail", FailingMockAdapter)
    yield
    _adapter_classes.pop("mock", None)
    _adapter_classes.pop("mock_fail", None)


@pytest.fixture
def manager():
    return ConnectionManager()


@pytest.mark.asyncio
async def test_create_connection(manager):
    result = await manager.create_connection("c1", "mock", {"simulated": True})
    assert result["connection_id"] == "c1"
    assert result["adapter_type"] == "mock"
    assert manager.connection_count == 1


@pytest.mark.asyncio
async def test_create_duplicate_raises(manager):
    await manager.create_connection("c1", "mock", {})
    with pytest.raises(ValueError, match="already exists"):
        await manager.create_connection("c1", "mock", {})


@pytest.mark.asyncio
async def test_create_unknown_type_raises(manager):
    with pytest.raises(ValueError, match="Unknown adapter type"):
        await manager.create_connection("c1", "nonexistent", {})


@pytest.mark.asyncio
async def test_remove_connection(manager):
    await manager.create_connection("c1", "mock", {})
    assert manager.connection_count == 1
    removed = await manager.remove_connection("c1")
    assert removed is True
    assert manager.connection_count == 0


@pytest.mark.asyncio
async def test_remove_nonexistent(manager):
    removed = await manager.remove_connection("nope")
    assert removed is False


@pytest.mark.asyncio
async def test_get_connection(manager):
    await manager.create_connection("c1", "mock", {})
    adapter = manager.get_connection("c1")
    assert adapter is not None
    assert adapter.adapter_type == "mock"


@pytest.mark.asyncio
async def test_get_nonexistent(manager):
    assert manager.get_connection("nope") is None


@pytest.mark.asyncio
async def test_list_connections(manager):
    await manager.create_connection("c1", "mock", {})
    await manager.create_connection("c2", "mock", {})
    conns = manager.list_connections()
    assert len(conns) == 2
    ids = {c["connection_id"] for c in conns}
    assert ids == {"c1", "c2"}


@pytest.mark.asyncio
async def test_health_aggregation(manager):
    await manager.create_connection("c1", "mock", {})
    # Allow adapter background task to run
    await asyncio.sleep(0.1)
    agg = await manager.health()
    assert agg["connection_count"] == 1
    assert "c1" in agg["adapters"]


@pytest.mark.asyncio
async def test_send_to(manager):
    await manager.create_connection("c1", "mock", {})
    result = await manager.send_to("c1", {"type": "test"})
    assert result is True


@pytest.mark.asyncio
async def test_send_to_nonexistent(manager):
    result = await manager.send_to("nope", {"type": "test"})
    assert result is False


@pytest.mark.asyncio
async def test_broadcast(manager):
    await manager.create_connection("c1", "mock", {})
    await manager.create_connection("c2", "mock", {})
    sent = await manager.broadcast({"type": "test"})
    assert sent == 2


@pytest.mark.asyncio
async def test_broadcast_filtered(manager):
    await manager.create_connection("c1", "mock", {})
    await manager.create_connection("c2", "mock_fail", {})
    sent = await manager.broadcast({"type": "test"}, adapter_type="mock")
    assert sent == 1


@pytest.mark.asyncio
async def test_stop_closes_all(manager):
    await manager.create_connection("c1", "mock", {})
    await manager.create_connection("c2", "mock", {})
    assert manager.connection_count == 2
    await manager.stop()
    assert manager.connection_count == 0
