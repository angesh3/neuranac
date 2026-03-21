"""Tests for BridgeAdapter base class and AdapterStatus."""
import pytest
from app.adapter_base import AdapterStatus, BridgeAdapter


class DummyAdapter(BridgeAdapter):
    """Concrete test adapter."""
    adapter_type = "dummy"

    async def connect(self) -> bool:
        self.status = AdapterStatus.CONNECTED
        return True

    async def disconnect(self) -> None:
        self.status = AdapterStatus.DISCONNECTED

    async def health(self) -> dict:
        return {"status": self.status.value}

    async def send(self, message: dict) -> bool:
        return True


class FailAdapter(BridgeAdapter):
    """Adapter that always fails to connect."""
    adapter_type = "fail"

    async def connect(self) -> bool:
        self.set_error("connection refused")
        return False

    async def disconnect(self) -> None:
        self.status = AdapterStatus.DISCONNECTED

    async def health(self) -> dict:
        return {"status": self.status.value, "error": self._error}

    async def send(self, message: dict) -> bool:
        return False


def test_adapter_status_enum():
    assert AdapterStatus.CONNECTED.value == "connected"
    assert AdapterStatus.DISCONNECTED.value == "disconnected"
    assert AdapterStatus.RECONNECTING.value == "reconnecting"
    assert AdapterStatus.ERROR.value == "error"
    assert AdapterStatus.INITIALIZING.value == "initializing"
    assert AdapterStatus.DRAINING.value == "draining"


def test_adapter_init():
    adapter = DummyAdapter(connection_id="test-1", config={"foo": "bar"})
    assert adapter.connection_id == "test-1"
    assert adapter.adapter_type == "dummy"
    assert adapter.config == {"foo": "bar"}
    assert adapter.status == AdapterStatus.INITIALIZING
    assert adapter._error is None


@pytest.mark.asyncio
async def test_adapter_connect():
    adapter = DummyAdapter(connection_id="test-2", config={})
    result = await adapter.connect()
    assert result is True
    assert adapter.status == AdapterStatus.CONNECTED


@pytest.mark.asyncio
async def test_adapter_disconnect():
    adapter = DummyAdapter(connection_id="test-3", config={})
    await adapter.connect()
    await adapter.disconnect()
    assert adapter.status == AdapterStatus.DISCONNECTED


@pytest.mark.asyncio
async def test_adapter_health():
    adapter = DummyAdapter(connection_id="test-4", config={})
    await adapter.connect()
    h = await adapter.health()
    assert h["status"] == "connected"


@pytest.mark.asyncio
async def test_adapter_send():
    adapter = DummyAdapter(connection_id="test-5", config={})
    result = await adapter.send({"type": "test"})
    assert result is True


@pytest.mark.asyncio
async def test_adapter_on_message_default():
    adapter = DummyAdapter(connection_id="test-6", config={})
    # Default on_message is a no-op — should not raise
    await adapter.on_message({"type": "test"})


def test_adapter_get_status():
    adapter = DummyAdapter(connection_id="test-7", config={})
    status = adapter.get_status()
    assert status["connection_id"] == "test-7"
    assert status["adapter_type"] == "dummy"
    assert status["status"] == "initializing"
    assert status["error"] is None


def test_adapter_set_error():
    adapter = DummyAdapter(connection_id="test-8", config={})
    adapter.set_error("something broke")
    assert adapter.status == AdapterStatus.ERROR
    assert adapter._error == "something broke"
    status = adapter.get_status()
    assert status["error"] == "something broke"


@pytest.mark.asyncio
async def test_fail_adapter_connect():
    adapter = FailAdapter(connection_id="fail-1", config={})
    result = await adapter.connect()
    assert result is False
    assert adapter.status == AdapterStatus.ERROR
    assert adapter._error == "connection refused"


def test_adapter_repr():
    adapter = DummyAdapter(connection_id="repr-1", config={})
    assert "DummyAdapter" in repr(adapter)
    assert "repr-1" in repr(adapter)
    assert "initializing" in repr(adapter)
