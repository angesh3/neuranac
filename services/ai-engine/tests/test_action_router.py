"""Tests for ActionRouter — intent matching, navigation, field extraction, fallback."""
import pytest
from app.action_router import ActionRouter


@pytest.fixture
def router():
    return ActionRouter()


class TestPatternMatching:
    @pytest.mark.asyncio
    async def test_navigation_intent(self, router):
        result = await router.route("go to policies")
        assert result["type"] == "navigation"
        assert result["route"] == "/policies"

    @pytest.mark.asyncio
    async def test_navigation_legacy_nac(self, router):
        result = await router.route("open legacy nac")
        assert result["type"] == "navigation"
        assert result["route"] == "/legacy-nac"

    @pytest.mark.asyncio
    async def test_list_devices_intent(self, router):
        # Without API Gateway running, this will hit an error but intent matching works
        result = await router.route("show all network devices")
        assert result["intent"] == "list_devices"

    @pytest.mark.asyncio
    async def test_list_sessions_intent(self, router):
        result = await router.route("show active sessions")
        assert result["intent"] in ("list_sessions", "failed_sessions", "session_count")

    @pytest.mark.asyncio
    async def test_shadow_ai_intent(self, router):
        result = await router.route("show shadow ai detections")
        assert result["intent"] == "shadow_detections"

    @pytest.mark.asyncio
    async def test_unknown_intent_fallback(self, router):
        result = await router.route("xyzzy nonsense query 12345")
        assert result["type"] == "text"
        assert result["intent"] == "unknown"
        assert "I'm not sure" in result["message"]


class TestFieldExtraction:
    @pytest.mark.asyncio
    async def test_extract_name_quoted(self, router):
        body = await router._extract_fields(
            {"intent": "create_policy", "extract_fields": ["name"]},
            'create policy named "Corp-Access"'
        )
        assert body["name"] == "Corp-Access"

    @pytest.mark.asyncio
    async def test_extract_ip_address(self, router):
        body = await router._extract_fields(
            {"intent": "add_device", "extract_fields": ["ip_address"]},
            "add switch 10.0.0.1"
        )
        assert body["ip_address"] == "10.0.0.1"

    @pytest.mark.asyncio
    async def test_extract_subnet(self, router):
        body = await router._extract_fields(
            {"intent": "discover_devices", "extract_fields": ["subnet"]},
            "discover devices on 192.168.1.0/24"
        )
        assert body["subnet"] == "192.168.1.0/24"

    @pytest.mark.asyncio
    async def test_extract_vendor(self, router):
        body = await router._extract_fields(
            {"intent": "add_device", "extract_fields": ["vendor"]},
            "add a cisco switch"
        )
        assert body["vendor"] == "cisco"

    @pytest.mark.asyncio
    async def test_extract_action_block(self, router):
        body = await router._extract_fields(
            {"intent": "create_ai_policy", "extract_fields": ["action", "service_type"]},
            "block openai traffic"
        )
        assert body["action"] == "block"
        assert body["service_type"] == "openai"


class TestFormatResponse:
    def test_error_response(self, router):
        msg = router._format_response(
            {"intent": "test", "description": "Test"},
            {"error": "not found"}, 404
        )
        assert "failed" in msg.lower()

    def test_list_response(self, router):
        msg = router._format_response(
            {"intent": "list_devices", "description": "List devices"},
            {"items": [{"id": "1"}], "total": 1}, 200
        )
        assert "1 result" in msg

    def test_empty_list_response(self, router):
        msg = router._format_response(
            {"intent": "list_devices", "description": "List network devices"},
            {"items": [], "total": 0}, 200
        )
        assert "No results" in msg


class TestFallback:
    def test_fallback_response_content(self, router):
        msg = router._fallback_response("hello")
        assert "View & Manage" in msg
        assert "Troubleshoot" in msg
