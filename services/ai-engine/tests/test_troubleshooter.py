"""Tests for AITroubleshooter — issue analysis patterns."""
import pytest
from app.troubleshooter import AITroubleshooter


@pytest.fixture
def troubleshooter():
    return AITroubleshooter()


class TestAnalyze:
    @pytest.mark.asyncio
    async def test_auth_failure(self, troubleshooter):
        result = await troubleshooter.analyze({
            "query": "authentication failure for user jdoe",
            "session_id": "sess-1",
            "username": "jdoe",
            "endpoint_mac": "AA:BB:CC:DD:EE:FF",
        })
        assert result["root_cause"] == "Authentication failure detected"
        assert len(result["recommended_fixes"]) > 0
        assert any("jdoe" in e for e in result["evidence"])

    @pytest.mark.asyncio
    async def test_vlan_assignment(self, troubleshooter):
        result = await troubleshooter.analyze({"query": "wrong VLAN assignment"})
        assert result["root_cause"] == "Incorrect authorization profile assignment"
        assert len(result["recommended_fixes"]) >= 3

    @pytest.mark.asyncio
    async def test_coa_issue(self, troubleshooter):
        result = await troubleshooter.analyze({"query": "CoA reauthentication not working"})
        assert result["root_cause"] == "CoA/Reauthentication issue"

    @pytest.mark.asyncio
    async def test_shadow_ai(self, troubleshooter):
        result = await troubleshooter.analyze({"query": "shadow AI service detected"})
        assert result["root_cause"] == "Shadow AI service detected"

    @pytest.mark.asyncio
    async def test_performance(self, troubleshooter):
        result = await troubleshooter.analyze({"query": "slow authentication latency"})
        assert result["root_cause"] == "Performance degradation"

    @pytest.mark.asyncio
    async def test_general_fallback(self, troubleshooter):
        result = await troubleshooter.analyze({"query": "something unknown happened"})
        assert result["root_cause"] == "General troubleshooting"
        assert len(result["recommended_fixes"]) > 0

    @pytest.mark.asyncio
    async def test_response_structure(self, troubleshooter):
        result = await troubleshooter.analyze({"query": "test"})
        assert "root_cause" in result
        assert "explanation" in result
        assert "recommended_fixes" in result
        assert "evidence" in result
