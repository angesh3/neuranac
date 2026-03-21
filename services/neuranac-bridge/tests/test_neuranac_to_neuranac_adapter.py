"""Tests for NeuraNAC-to-NeuraNAC Adapter — cross-site communication."""
import pytest
from app.adapters.neuranac_to_neuranac_adapter import NeuraNACToNeuraNACAdapter
from app.adapter_base import AdapterStatus


@pytest.fixture
def neuranac_config():
    return {
        "simulated": True,
        "peer_api_url": "http://peer-neuranac:8080",
        "peer_grpc_address": "peer-neuranac:9090",
        "nats_url": "nats://localhost:4222",
        "site_id": "site-001",
        "tenant_id": "tenant-001",
        "deployment_mode": "hybrid",
        "site_type": "onprem",
    }


@pytest.mark.asyncio
async def test_neuranac_to_neuranac_connect_simulated(neuranac_config):
    adapter = NeuraNACToNeuraNACAdapter(connection_id="neuranac-1", config=neuranac_config)
    result = await adapter.connect()
    assert result is True
    assert adapter.status == AdapterStatus.CONNECTED


@pytest.mark.asyncio
async def test_neuranac_to_neuranac_disconnect(neuranac_config):
    adapter = NeuraNACToNeuraNACAdapter(connection_id="neuranac-2", config=neuranac_config)
    await adapter.connect()
    await adapter.disconnect()
    assert adapter.status == AdapterStatus.DISCONNECTED


@pytest.mark.asyncio
async def test_neuranac_to_neuranac_health(neuranac_config):
    adapter = NeuraNACToNeuraNACAdapter(connection_id="neuranac-3", config=neuranac_config)
    await adapter.connect()
    h = await adapter.health()
    assert h["status"] == "connected"
    assert h["simulated"] is True
    assert h["peer_api_url"] == "http://peer-neuranac:8080"
    assert h["site_type"] == "onprem"


@pytest.mark.asyncio
async def test_neuranac_to_neuranac_proxy_http_simulated(neuranac_config):
    adapter = NeuraNACToNeuraNACAdapter(connection_id="neuranac-4", config=neuranac_config)
    await adapter.connect()
    result = await adapter.proxy_http_request("GET", "/api/v1/health")
    assert result["status_code"] == 200
    assert "simulated" in result["body"]


@pytest.mark.asyncio
async def test_neuranac_to_neuranac_send_http_proxy(neuranac_config):
    adapter = NeuraNACToNeuraNACAdapter(connection_id="neuranac-5", config=neuranac_config)
    await adapter.connect()
    result = await adapter.send({
        "type": "http_proxy",
        "method": "GET",
        "path": "/api/v1/policies",
    })
    assert result is True


@pytest.mark.asyncio
async def test_neuranac_to_neuranac_send_grpc_sync(neuranac_config):
    adapter = NeuraNACToNeuraNACAdapter(connection_id="neuranac-6", config=neuranac_config)
    await adapter.connect()
    result = await adapter.send({
        "type": "grpc_sync",
        "data": {"entity": "policies"},
    })
    assert result is True


@pytest.mark.asyncio
async def test_neuranac_to_neuranac_send_nats_event(neuranac_config):
    adapter = NeuraNACToNeuraNACAdapter(connection_id="neuranac-7", config=neuranac_config)
    await adapter.connect()
    result = await adapter.send({
        "type": "nats_event",
        "data": {"event": "session_started"},
    })
    assert result is True


@pytest.mark.asyncio
async def test_neuranac_to_neuranac_send_default(neuranac_config):
    adapter = NeuraNACToNeuraNACAdapter(connection_id="neuranac-8", config=neuranac_config)
    await adapter.connect()
    result = await adapter.send({"type": "something_else", "data": {}})
    assert result is True  # Falls through to NATS broadcast


@pytest.mark.asyncio
async def test_neuranac_to_neuranac_messages_counter(neuranac_config):
    adapter = NeuraNACToNeuraNACAdapter(connection_id="neuranac-9", config=neuranac_config)
    await adapter.connect()
    await adapter.send({"type": "nats_event", "data": {}})
    await adapter.send({"type": "grpc_sync", "data": {}})
    h = await adapter.health()
    assert h["messages_sent"] == 2


def test_neuranac_to_neuranac_adapter_type():
    adapter = NeuraNACToNeuraNACAdapter(connection_id="neuranac-10", config={"simulated": True})
    assert adapter.adapter_type == "neuranac_to_neuranac"
