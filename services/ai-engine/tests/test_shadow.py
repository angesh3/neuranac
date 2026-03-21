"""Tests for Shadow AI Detection"""
import pytest
from app.shadow import ShadowAIDetector


@pytest.fixture
def detector():
    d = ShadowAIDetector()
    # Load only built-in signatures (no DB)
    d.signatures = [
        {"name": "OpenAI ChatGPT", "category": "llm", "dns": ["api.openai.com", "chat.openai.com"], "risk": "high"},
        {"name": "GitHub Copilot", "category": "coding", "dns": ["copilot.github.com"], "risk": "medium"},
        {"name": "AWS Bedrock", "category": "cloud_ai", "dns": ["bedrock-runtime.amazonaws.com"], "risk": "low"},
    ]
    d.approved_services = {"AWS Bedrock"}
    return d


class TestShadowAIDetector:
    @pytest.mark.asyncio
    async def test_detect_openai(self, detector):
        result = await detector.detect({"destination_domain": "api.openai.com"})
        assert result["is_ai_service"] is True
        assert result["service_name"] == "OpenAI ChatGPT"
        assert result["risk_level"] == "high"
        assert result["recommended_action"] == "block"

    @pytest.mark.asyncio
    async def test_detect_approved_service(self, detector):
        result = await detector.detect({"destination_domain": "bedrock-runtime.amazonaws.com"})
        assert result["is_ai_service"] is True
        assert result["is_approved"] is True
        assert result["risk_level"] == "low"
        assert result["recommended_action"] == "allow"

    @pytest.mark.asyncio
    async def test_detect_copilot(self, detector):
        result = await detector.detect({"sni": "copilot.github.com"})
        assert result["is_ai_service"] is True
        assert result["service_category"] == "coding"

    @pytest.mark.asyncio
    async def test_no_match(self, detector):
        result = await detector.detect({"destination_domain": "google.com"})
        assert result["is_ai_service"] is False
        assert result["recommended_action"] == "allow"

    @pytest.mark.asyncio
    async def test_local_llm_api_pattern(self, detector):
        result = await detector.detect({"destination_domain": "192.168.1.100", "http_path": "/v1/chat/completions"})
        assert result["is_ai_service"] is True
        assert result["service_category"] == "local_llm"

    @pytest.mark.asyncio
    async def test_empty_request(self, detector):
        result = await detector.detect({})
        assert result["is_ai_service"] is False
