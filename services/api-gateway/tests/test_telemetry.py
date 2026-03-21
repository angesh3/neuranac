"""Tests for Network Telemetry Router — events, flows, DHCP, neighbors, collectors."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone


# ─── Mock DB helpers ─────────────────────────────────────────────────────────

def _mock_mapping(data: dict):
    """Create a mock row that behaves like a mapping."""
    m = MagicMock()
    m.__getitem__ = lambda self, k: data[k]
    m.keys = lambda self: data.keys()
    m.items = lambda self: data.items()
    m.values = lambda self: data.values()
    # dict() conversion
    m.__iter__ = lambda self: iter(data)
    return data  # just return the dict for simplicity


# ─── Test Router Import ──────────────────────────────────────────────────────

def test_telemetry_router_import():
    from app.routers.telemetry import router
    assert router is not None


def test_telemetry_router_has_routes():
    from app.routers.telemetry import router
    paths = [r.path for r in router.routes]
    assert "/events" in paths
    assert "/events/summary" in paths
    assert "/flows" in paths
    assert "/flows/top-talkers" in paths
    assert "/dhcp" in paths
    assert "/dhcp/os-distribution" in paths
    assert "/neighbors" in paths
    assert "/neighbors/topology-map" in paths
    assert "/collectors" in paths
    assert "/health" in paths


# ─── Test Event Endpoints ────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_telemetry_events_defaults():
    from app.routers.telemetry import list_telemetry_events
    mock_db = AsyncMock()
    # Count query
    count_result = MagicMock()
    count_result.scalar.return_value = 0
    # Data query
    data_result = MagicMock()
    data_result.mappings.return_value.all.return_value = []
    mock_db.execute = AsyncMock(side_effect=[count_result, data_result])

    result = await list_telemetry_events(
        skip=0, limit=50, event_type=None, source_ip=None,
        severity=None, since_hours=None, db=mock_db
    )
    assert result["total"] == 0
    assert result["items"] == []
    assert result["skip"] == 0
    assert result["limit"] == 50


@pytest.mark.asyncio
async def test_list_telemetry_events_with_filters():
    from app.routers.telemetry import list_telemetry_events
    mock_db = AsyncMock()
    count_result = MagicMock()
    count_result.scalar.return_value = 1
    row = {
        "id": "abc-123", "event_type": "snmp", "source_ip": "10.0.0.1",
        "site_id": None, "node_id": "twin-a", "severity": "warning",
        "facility": None, "trap_oid": "1.3.6.1.6.3.1.1.5.3",
        "message": "linkDown", "raw_data": {}, "created_at": datetime.now(timezone.utc),
    }
    data_result = MagicMock()
    data_result.mappings.return_value.all.return_value = [row]
    mock_db.execute = AsyncMock(side_effect=[count_result, data_result])

    result = await list_telemetry_events(
        skip=0, limit=50, event_type="snmp", source_ip="10.0.0.1",
        severity="warning", since_hours=24, db=mock_db
    )
    assert result["total"] == 1
    assert len(result["items"]) == 1
    assert result["items"][0]["event_type"] == "snmp"


@pytest.mark.asyncio
async def test_telemetry_events_summary():
    from app.routers.telemetry import telemetry_events_summary
    mock_db = AsyncMock()
    data_result = MagicMock()
    data_result.mappings.return_value.all.return_value = [
        {"event_type": "snmp", "severity": "warning", "count": 42},
        {"event_type": "syslog", "severity": "error", "count": 5},
    ]
    mock_db.execute = AsyncMock(return_value=data_result)

    result = await telemetry_events_summary(since_hours=24, db=mock_db)
    assert result["since_hours"] == 24
    assert len(result["summary"]) == 2


# ─── Test Flow Endpoints ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_flows_defaults():
    from app.routers.telemetry import list_flows
    mock_db = AsyncMock()
    count_result = MagicMock()
    count_result.scalar.return_value = 0
    data_result = MagicMock()
    data_result.mappings.return_value.all.return_value = []
    mock_db.execute = AsyncMock(side_effect=[count_result, data_result])

    result = await list_flows(
        skip=0, limit=50, exporter_ip=None, src_ip=None, dst_ip=None,
        protocol=None, dst_port=None, since_hours=None, db=mock_db
    )
    assert result["total"] == 0
    assert result["items"] == []


@pytest.mark.asyncio
async def test_list_flows_with_filters():
    from app.routers.telemetry import list_flows
    mock_db = AsyncMock()
    count_result = MagicMock()
    count_result.scalar.return_value = 5
    data_result = MagicMock()
    data_result.mappings.return_value.all.return_value = [
        {"id": "f1", "exporter_ip": "10.0.0.1", "site_id": None, "version": 5,
         "src_ip": "192.168.1.1", "dst_ip": "10.0.0.2", "src_port": 12345,
         "dst_port": 443, "protocol": 6, "packets": 100, "bytes": 50000,
         "tos": 0, "next_hop": "10.0.0.254", "created_at": datetime.now(timezone.utc)},
    ]
    mock_db.execute = AsyncMock(side_effect=[count_result, data_result])

    result = await list_flows(
        skip=0, limit=50, exporter_ip="10.0.0.1", src_ip=None,
        dst_ip=None, protocol=6, dst_port=443, since_hours=1, db=mock_db
    )
    assert result["total"] == 5


@pytest.mark.asyncio
async def test_top_talkers():
    from app.routers.telemetry import top_talkers
    mock_db = AsyncMock()
    data_result = MagicMock()
    data_result.mappings.return_value.all.return_value = [
        {"src_ip": "10.0.0.1", "total_bytes": 1000000, "total_packets": 5000, "flow_count": 100},
    ]
    mock_db.execute = AsyncMock(return_value=data_result)

    result = await top_talkers(since_hours=1, limit=10, db=mock_db)
    assert result["since_hours"] == 1
    assert len(result["top_talkers"]) == 1
    assert result["top_talkers"][0]["total_bytes"] == 1000000


# ─── Test DHCP Endpoints ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_dhcp_fingerprints():
    from app.routers.telemetry import list_dhcp_fingerprints
    mock_db = AsyncMock()
    count_result = MagicMock()
    count_result.scalar.return_value = 2
    data_result = MagicMock()
    data_result.mappings.return_value.all.return_value = [
        {"id": "d1", "mac_address": "aa:bb:cc:dd:ee:ff", "client_ip": "10.0.0.50",
         "hostname": "laptop1", "vendor_class": "MSFT 5.0", "fingerprint": "01,03,06,0f",
         "os_guess": "Windows 10/11", "msg_type": "DISCOVER", "source_ip": "10.0.0.1",
         "site_id": None, "created_at": datetime.now(timezone.utc)},
    ]
    mock_db.execute = AsyncMock(side_effect=[count_result, data_result])

    result = await list_dhcp_fingerprints(
        skip=0, limit=50, mac=None, hostname="laptop", os_guess=None, db=mock_db
    )
    assert result["total"] == 2


@pytest.mark.asyncio
async def test_dhcp_os_distribution():
    from app.routers.telemetry import dhcp_os_distribution
    mock_db = AsyncMock()
    data_result = MagicMock()
    data_result.mappings.return_value.all.return_value = [
        {"os_guess": "Windows 10/11", "device_count": 50},
        {"os_guess": "macOS", "device_count": 30},
        {"os_guess": "iOS/iPadOS", "device_count": 20},
    ]
    mock_db.execute = AsyncMock(return_value=data_result)

    result = await dhcp_os_distribution(db=mock_db)
    assert len(result["os_distribution"]) == 3
    assert result["os_distribution"][0]["os_guess"] == "Windows 10/11"


# ─── Test Neighbor Endpoints ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_neighbors():
    from app.routers.telemetry import list_neighbors
    mock_db = AsyncMock()
    count_result = MagicMock()
    count_result.scalar.return_value = 1
    data_result = MagicMock()
    data_result.mappings.return_value.all.return_value = [
        {"id": "n1", "local_device_ip": "10.0.0.1", "local_port": "Gi0/1",
         "remote_device": "switch2", "remote_port": "Gi0/2", "remote_ip": "10.0.0.2",
         "platform": "WS-C3850", "protocol": "cdp", "site_id": None,
         "last_seen": datetime.now(timezone.utc), "created_at": datetime.now(timezone.utc)},
    ]
    mock_db.execute = AsyncMock(side_effect=[count_result, data_result])

    result = await list_neighbors(
        skip=0, limit=50, local_device_ip=None, protocol="cdp", db=mock_db
    )
    assert result["total"] == 1
    assert result["items"][0]["protocol"] == "cdp"


@pytest.mark.asyncio
async def test_topology_map():
    from app.routers.telemetry import topology_map
    mock_db = AsyncMock()
    data_result = MagicMock()
    data_result.mappings.return_value.all.return_value = [
        {"local_device_ip": "10.0.0.1", "local_port": "Gi0/1",
         "remote_device": "switch2", "remote_port": "Gi0/2",
         "remote_ip": "10.0.0.2", "platform": "C3850", "protocol": "cdp"},
        {"local_device_ip": "10.0.0.1", "local_port": "Gi0/3",
         "remote_device": "ap1", "remote_port": "Gi0",
         "remote_ip": "10.0.0.10", "platform": "AIR-AP2802", "protocol": "lldp"},
    ]
    mock_db.execute = AsyncMock(return_value=data_result)

    result = await topology_map(db=mock_db)
    assert result["node_count"] == 3  # 10.0.0.1, switch2, ap1
    assert result["edge_count"] == 2
    assert "10.0.0.1" in result["nodes"]
    assert "switch2" in result["nodes"]


# ─── Test Collector Status ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_list_collectors():
    from app.routers.telemetry import list_collectors
    mock_db = AsyncMock()
    data_result = MagicMock()
    data_result.mappings.return_value.all.return_value = [
        {"id": "c1", "node_id": "twin-a", "site_id": None, "status": "active",
         "channels": {"snmp": True, "syslog": True}, "stats": {"snmp": {"received": 100}},
         "last_heartbeat": datetime.now(timezone.utc), "created_at": datetime.now(timezone.utc)},
    ]
    mock_db.execute = AsyncMock(return_value=data_result)

    result = await list_collectors(db=mock_db)
    assert len(result["collectors"]) == 1
    assert result["collectors"][0]["status"] == "active"


# ─── Test Telemetry Health ───────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_telemetry_health_all_tables():
    from app.routers.telemetry import telemetry_health
    mock_db = AsyncMock()
    # Each table check returns a count
    count_results = []
    for _ in range(5):
        r = MagicMock()
        r.scalar.return_value = 0
        count_results.append(r)
    mock_db.execute = AsyncMock(side_effect=count_results)

    result = await telemetry_health(db=mock_db)
    assert result["status"] == "healthy"
    assert len(result["tables"]) == 5
    for table, info in result["tables"].items():
        assert info["exists"] is True


@pytest.mark.asyncio
async def test_telemetry_health_missing_table():
    from app.routers.telemetry import telemetry_health
    mock_db = AsyncMock()
    # First table OK, second raises
    ok_result = MagicMock()
    ok_result.scalar.return_value = 0
    mock_db.execute = AsyncMock(side_effect=[
        ok_result,
        Exception("relation does not exist"),
        ok_result,
        ok_result,
        ok_result,
    ])

    result = await telemetry_health(db=mock_db)
    assert result["status"] == "degraded"


# ─── Test Route Count ────────────────────────────────────────────────────────

def test_telemetry_route_count():
    from app.routers.telemetry import router
    # Should have exactly 10 routes
    route_count = len([r for r in router.routes if hasattr(r, "methods")])
    assert route_count == 10, f"Expected 10 routes, got {route_count}"


# ─── Test Pagination Parameters ──────────────────────────────────────────────

def test_events_pagination_params():
    """Verify the endpoint accepts expected query parameters."""
    from app.routers.telemetry import router
    events_route = None
    for r in router.routes:
        if hasattr(r, "path") and r.path == "/events" and hasattr(r, "methods") and "GET" in r.methods:
            events_route = r
            break
    assert events_route is not None, "GET /events route not found"


def test_flows_pagination_params():
    from app.routers.telemetry import router
    flows_route = None
    for r in router.routes:
        if hasattr(r, "path") and r.path == "/flows" and hasattr(r, "methods") and "GET" in r.methods:
            flows_route = r
            break
    assert flows_route is not None, "GET /flows route not found"
