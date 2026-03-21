"""Tests for NLP Policy Assistant (template matching fallback)"""
import pytest
from app.nlp_policy import NLPolicyAssistant


@pytest.fixture
def assistant():
    return NLPolicyAssistant()


class TestNLPolicyTemplateMatching:
    def test_block_ai(self, assistant):
        result = assistant._template_match("Block all shadow AI traffic")
        assert result["success"] is True
        assert len(result["rules"]) == 1
        assert result["rules"][0]["action"] == "deny"
        assert result["rules"][0]["name"] == "Block AI Traffic"

    def test_allow_employees(self, assistant):
        result = assistant._template_match("Allow employees full network access")
        assert result["success"] is True
        assert result["rules"][0]["action"] == "permit"
        assert result["rules"][0]["conditions"][0]["attribute"] == "identity.groups"

    def test_guest_access(self, assistant):
        result = assistant._template_match("Set up guest access for visitors")
        assert result["success"] is True
        assert result["rules"][0]["name"] == "Guest Access"
        assert result["rules"][0]["action"] == "permit"

    def test_quarantine_noncompliant(self, assistant):
        result = assistant._template_match("Quarantine noncompliant endpoints")
        assert result["success"] is True
        assert result["rules"][0]["action"] == "quarantine"

    def test_no_match(self, assistant):
        result = assistant._template_match("something completely unrelated xyz123")
        assert result["success"] is False
        assert len(result["rules"]) == 0
        assert result["confidence"] == "low"

    def test_confidence_when_matched(self, assistant):
        result = assistant._template_match("Block AI traffic on network")
        assert result["confidence"] == "medium"

    @pytest.mark.asyncio
    async def test_translate_empty_input(self, assistant):
        result = await assistant.translate("")
        assert result["success"] is False
        assert len(result["rules"]) == 0

    @pytest.mark.asyncio
    async def test_translate_falls_back_to_template(self, assistant):
        """When LLM is unavailable, should fall back to template matching"""
        result = await assistant.translate("Block all shadow AI traffic")
        assert result["success"] is True
        assert len(result["rules"]) >= 1
