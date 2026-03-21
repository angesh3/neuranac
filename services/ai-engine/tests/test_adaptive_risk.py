"""Tests for AdaptiveRiskEngine — thresholds, feedback, calibration."""
import pytest
from app.adaptive_risk import AdaptiveRiskEngine, DEFAULT_THRESHOLDS


@pytest.fixture
def engine():
    return AdaptiveRiskEngine()


class TestDefaultThresholds:
    def test_default_values(self, engine):
        t = engine.get_thresholds()
        assert t["quarantine"] == 70
        assert t["monitor"] == 40
        assert t["allow"] == 0

    def test_unknown_tenant_gets_defaults(self, engine):
        t = engine.get_thresholds("nonexistent-tenant")
        assert t == DEFAULT_THRESHOLDS


class TestFeedback:
    @pytest.mark.asyncio
    async def test_record_feedback(self, engine):
        result = await engine.record_feedback("t1", 75, "quarantine", True)
        assert result["status"] == "recorded"
        assert result["feedback_count"] == 1

    @pytest.mark.asyncio
    async def test_feedback_accumulates(self, engine):
        for i in range(5):
            await engine.record_feedback("t1", 50 + i, "monitor", True)
        result = await engine.record_feedback("t1", 60, "monitor", False)
        assert result["feedback_count"] == 6

    @pytest.mark.asyncio
    async def test_feedback_max_limit(self, engine):
        engine._max_feedback = 10
        for i in range(15):
            await engine.record_feedback("t1", 50, "monitor", True)
        assert len(engine._feedback["t1"]) <= 10


class TestCalibration:
    def test_calibrate_raises_quarantine_on_fp(self, engine):
        feedback = []
        # 5 false-positive quarantines at score 60
        for _ in range(5):
            feedback.append({"risk_score": 60, "decision": "quarantine", "was_correct": False, "timestamp": 0})
        # Some correct quarantines
        for _ in range(10):
            feedback.append({"risk_score": 80, "decision": "quarantine", "was_correct": True, "timestamp": 0})
        for _ in range(10):
            feedback.append({"risk_score": 30, "decision": "allow", "was_correct": True, "timestamp": 0})

        thresholds = engine._calibrate(feedback)
        # Should raise quarantine threshold above default 70
        assert thresholds["quarantine"] >= 70

    def test_calibrate_lowers_monitor_on_fn(self, engine):
        feedback = []
        # 5 false-negative allows at score 35
        for _ in range(5):
            feedback.append({"risk_score": 35, "decision": "allow", "was_correct": False, "timestamp": 0})
        for _ in range(15):
            feedback.append({"risk_score": 20, "decision": "allow", "was_correct": True, "timestamp": 0})
        for _ in range(5):
            feedback.append({"risk_score": 80, "decision": "quarantine", "was_correct": True, "timestamp": 0})

        thresholds = engine._calibrate(feedback)
        assert thresholds["monitor"] <= 40

    def test_quarantine_always_above_monitor(self, engine):
        feedback = []
        for _ in range(10):
            feedback.append({"risk_score": 50, "decision": "quarantine", "was_correct": False, "timestamp": 0})
        for _ in range(10):
            feedback.append({"risk_score": 50, "decision": "allow", "was_correct": False, "timestamp": 0})
        for _ in range(5):
            feedback.append({"risk_score": 80, "decision": "quarantine", "was_correct": True, "timestamp": 0})

        thresholds = engine._calibrate(feedback)
        assert thresholds["quarantine"] > thresholds["monitor"]


class TestStats:
    @pytest.mark.asyncio
    async def test_get_stats_empty(self, engine):
        stats = await engine.get_stats("t1")
        assert stats["feedback_count"] == 0
        assert stats["accuracy"] == 0

    @pytest.mark.asyncio
    async def test_get_stats_with_feedback(self, engine):
        await engine.record_feedback("t1", 75, "quarantine", True)
        await engine.record_feedback("t1", 30, "allow", False)
        stats = await engine.get_stats("t1")
        assert stats["feedback_count"] == 2
        assert stats["accuracy"] == 0.5
        assert stats["false_negative_count"] == 1
