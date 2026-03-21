"""Tests for AI Endpoint Profiler (rule-based fallback)"""
import pytest
from app.profiler import EndpointProfiler


@pytest.fixture
def profiler():
    p = EndpointProfiler()
    # Ensure rule-based mode (no ONNX model)
    p.model = None
    p.model_loaded = False
    return p


class TestEndpointProfiler:
    @pytest.mark.asyncio
    async def test_apple_device_with_dns(self, profiler):
        result = await profiler.predict({
            "mac_address": "AA:BB:CC:DD:EE:FF",
            "oui_vendor": "Apple",
            "dns_queries": ["apple.com"],
        })
        assert result["device_type"] == "iphone"
        assert result["vendor"] == "Apple"
        assert result["os"] == "iOS"
        assert result["confidence"] >= 0.5

    @pytest.mark.asyncio
    async def test_apple_device_without_dns(self, profiler):
        result = await profiler.predict({
            "mac_address": "AA:BB:CC:DD:EE:FF",
            "oui_vendor": "Apple",
            "dns_queries": [],
        })
        assert result["device_type"] == "macos"
        assert result["os"] == "macOS"

    @pytest.mark.asyncio
    async def test_cisco_ip_phone(self, profiler):
        result = await profiler.predict({
            "mac_address": "00:00:0C:11:22:33",
            "oui_vendor": "Cisco",
            "ports_used": [5060],
        })
        assert result["device_type"] == "ip-phone"
        assert result["confidence"] >= 0.7

    @pytest.mark.asyncio
    async def test_cisco_switch(self, profiler):
        result = await profiler.predict({
            "mac_address": "00:00:0C:11:22:33",
            "oui_vendor": "Cisco",
            "ports_used": [22, 443],
        })
        assert result["device_type"] == "switch"

    @pytest.mark.asyncio
    async def test_printer_by_hostname(self, profiler):
        result = await profiler.predict({
            "mac_address": "AA:BB:CC:DD:EE:FF",
            "oui_vendor": "HP",
            "dhcp_attributes": {"hostname": "hp-printer-3f"},
        })
        assert result["device_type"] == "printer"

    @pytest.mark.asyncio
    async def test_printer_by_port(self, profiler):
        result = await profiler.predict({
            "mac_address": "AA:BB:CC:DD:EE:FF",
            "oui_vendor": "Unknown",
            "ports_used": [9100],
        })
        assert result["device_type"] == "printer"
        assert result["confidence"] >= 0.7

    @pytest.mark.asyncio
    async def test_camera_by_port(self, profiler):
        result = await profiler.predict({
            "mac_address": "AA:BB:CC:DD:EE:FF",
            "oui_vendor": "Unknown",
            "ports_used": [554],
        })
        assert result["device_type"] == "camera"

    @pytest.mark.asyncio
    async def test_ai_agent_by_dns(self, profiler):
        result = await profiler.predict({
            "mac_address": "AA:BB:CC:DD:EE:FF",
            "oui_vendor": "Unknown",
            "dns_queries": ["api.openai.com"],
        })
        assert result["device_type"] == "ai-agent"

    @pytest.mark.asyncio
    async def test_android_device(self, profiler):
        result = await profiler.predict({
            "mac_address": "AA:BB:CC:DD:EE:FF",
            "oui_vendor": "Samsung",
        })
        assert result["device_type"] == "android"
        assert result["os"] == "Android"

    @pytest.mark.asyncio
    async def test_unknown_device(self, profiler):
        result = await profiler.predict({
            "mac_address": "AA:BB:CC:DD:EE:FF",
            "oui_vendor": "Unknown",
        })
        assert result["device_type"] == "unknown"
        assert result["model_version"] == "rule-based-v1"

    @pytest.mark.asyncio
    async def test_empty_request(self, profiler):
        result = await profiler.predict({})
        assert "device_type" in result
        assert "confidence" in result
        assert "model_version" in result

    @pytest.mark.asyncio
    async def test_result_structure(self, profiler):
        result = await profiler.predict({"mac_address": "AA:BB:CC:DD:EE:FF", "oui_vendor": "Apple"})
        assert "device_type" in result
        assert "vendor" in result
        assert "os" in result
        assert "confidence" in result
        assert "top_candidates" in result
        assert "model_version" in result

    def test_guess_os(self, profiler):
        assert profiler._guess_os("windows-pc") == "Windows"
        assert profiler._guess_os("iphone") == "iOS"
        assert profiler._guess_os("server") == "Linux"
        assert profiler._guess_os("unknown") == "unknown"
