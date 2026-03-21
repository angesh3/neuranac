"""Tests for AI Risk Scoring Engine"""
import pytest
import asyncio
from app.risk import RiskScorer


@pytest.fixture
def scorer():
    return RiskScorer()


class TestRiskScorer:
    @pytest.mark.asyncio
    async def test_low_risk_clean_session(self, scorer):
        result = await scorer.compute({
            "username": "alice",
            "user_groups": ["employees"],
            "posture_status": "compliant",
            "failed_auth_count_24h": 0,
        })
        assert result["risk_level"] == "low"
        assert result["total_score"] < 30

    @pytest.mark.asyncio
    async def test_high_risk_shadow_ai(self, scorer):
        result = await scorer.compute({
            "username": "bob",
            "user_groups": ["employees"],
            "posture_status": "compliant",
            "shadow_ai_detected": True,
            "ai_delegation_depth": 3,
            "ai_data_upload_mb": 200,
        })
        assert result["risk_level"] in ("high", "critical")
        assert result["ai_activity_score"] > 10

    @pytest.mark.asyncio
    async def test_medium_risk_failed_auths(self, scorer):
        result = await scorer.compute({
            "username": "carol",
            "user_groups": ["contractors"],
            "posture_status": "unknown",
            "failed_auth_count_24h": 8,
        })
        assert result["total_score"] >= 25
        assert result["behavioral_score"] > 0

    @pytest.mark.asyncio
    async def test_noncompliant_endpoint(self, scorer):
        result = await scorer.compute({
            "username": "dave",
            "user_groups": ["employees"],
            "posture_status": "noncompliant",
        })
        assert result["endpoint_score"] >= 20

    @pytest.mark.asyncio
    async def test_empty_request(self, scorer):
        result = await scorer.compute({})
        assert "total_score" in result
        assert "risk_level" in result
        assert result["total_score"] >= 0

    @pytest.mark.asyncio
    async def test_score_capped_at_100(self, scorer):
        result = await scorer.compute({
            "failed_auth_count_24h": 100,
            "posture_status": "noncompliant",
            "shadow_ai_detected": True,
            "ai_delegation_depth": 10,
            "ai_data_upload_mb": 1000,
            "running_local_llm": True,
        })
        assert result["total_score"] <= 100

    @pytest.mark.asyncio
    async def test_risk_factors_populated(self, scorer):
        result = await scorer.compute({
            "shadow_ai_detected": True,
            "failed_auth_count_24h": 15,
            "posture_status": "noncompliant",
        })
        assert len(result["factors"]) >= 2
        categories = [f["category"] for f in result["factors"]]
        assert "behavioral" in categories or "ai_activity" in categories
