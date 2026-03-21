"""Tests for Anomaly Detection & Policy Drift modules"""
import pytest
import time
from unittest.mock import patch, AsyncMock
from app.anomaly import AnomalyDetector, PolicyDriftDetector, _std_dev


class TestStdDev:
    def test_single_value(self):
        assert _std_dev([5]) == 0.0

    def test_empty(self):
        assert _std_dev([]) == 0.0

    def test_identical_values(self):
        assert _std_dev([3, 3, 3, 3]) == 0.0

    def test_known_values(self):
        result = _std_dev([2, 4, 4, 4, 5, 5, 7, 9])
        assert 2.0 < result < 2.2  # sample stddev ~2.14


class TestAnomalyDetector:
    @pytest.fixture
    def detector(self):
        d = AnomalyDetector()
        return d

    @pytest.mark.asyncio
    async def test_no_baseline_no_anomaly(self, detector):
        """First observation should never be flagged as anomalous"""
        with patch("app.anomaly._get_redis", new_callable=AsyncMock, return_value=None):
            result = await detector.analyze({
                "endpoint_mac": "AA:BB:CC:DD:EE:FF",
                "username": "alice",
                "auth_time_hour": 10,
                "nas_ip": "10.0.0.1",
                "eap_type": "PEAP",
            })
        assert result["is_anomalous"] is False
        assert result["anomaly_score"] == 0
        assert result["recommendation"] == "allow"
        assert result["baseline_size"] == 1

    @pytest.mark.asyncio
    async def test_unusual_time_anomaly(self, detector):
        """Auth at 3am when baseline is all 9-17 should be flagged"""
        baseline = [
            {"hour": h, "nas_ip": "10.0.0.1", "eap_type": "PEAP", "timestamp": time.time() - i * 300}
            for i, h in enumerate([10, 11, 9, 14, 15, 10, 11])
        ]
        detector._baselines["alice"] = baseline

        with patch("app.anomaly._get_redis", new_callable=AsyncMock, return_value=None):
            result = await detector.analyze({
                "username": "alice",
                "auth_time_hour": 3,
                "nas_ip": "10.0.0.1",
                "eap_type": "PEAP",
            })
        assert result["is_anomalous"] is True
        anomaly_types = [a["type"] for a in result["anomalies"]]
        assert "unusual_time" in anomaly_types

    @pytest.mark.asyncio
    async def test_new_location_anomaly(self, detector):
        """Auth from a new NAS IP should be flagged"""
        baseline = [
            {"hour": 10, "nas_ip": "10.0.0.1", "eap_type": "PEAP", "timestamp": time.time() - i * 300}
            for i in range(6)
        ]
        detector._baselines["bob"] = baseline

        with patch("app.anomaly._get_redis", new_callable=AsyncMock, return_value=None):
            result = await detector.analyze({
                "username": "bob",
                "auth_time_hour": 10,
                "nas_ip": "192.168.99.1",
                "eap_type": "PEAP",
            })
        anomaly_types = [a["type"] for a in result["anomalies"]]
        assert "new_location" in anomaly_types

    @pytest.mark.asyncio
    async def test_eap_type_change(self, detector):
        """Switching EAP type should be flagged"""
        baseline = [
            {"hour": 10, "nas_ip": "10.0.0.1", "eap_type": "PEAP", "timestamp": time.time() - i * 300}
            for i in range(6)
        ]
        detector._baselines["carol"] = baseline

        with patch("app.anomaly._get_redis", new_callable=AsyncMock, return_value=None):
            result = await detector.analyze({
                "username": "carol",
                "auth_time_hour": 10,
                "nas_ip": "10.0.0.1",
                "eap_type": "EAP-TLS",
            })
        anomaly_types = [a["type"] for a in result["anomalies"]]
        assert "eap_type_change" in anomaly_types

    @pytest.mark.asyncio
    async def test_recommendation_quarantine(self, detector):
        """High anomaly score should recommend quarantine"""
        baseline = [
            {"hour": 14, "nas_ip": "10.0.0.1", "eap_type": "PEAP", "timestamp": time.time() - i * 300}
            for i in range(10)
        ]
        detector._baselines["dave"] = baseline

        with patch("app.anomaly._get_redis", new_callable=AsyncMock, return_value=None):
            result = await detector.analyze({
                "username": "dave",
                "auth_time_hour": 3,
                "nas_ip": "192.168.99.1",
                "eap_type": "MAB",
            })
        assert result["anomaly_score"] >= 25
        assert result["recommendation"] in ("monitor", "quarantine")

    @pytest.mark.asyncio
    async def test_baseline_window_cap(self, detector):
        """Baseline should not exceed max_window"""
        detector._max_window = 5
        detector._baselines["test"] = [{"hour": 10, "timestamp": time.time()} for _ in range(5)]

        with patch("app.anomaly._get_redis", new_callable=AsyncMock, return_value=None):
            await detector.analyze({"username": "test", "auth_time_hour": 10})
        assert len(detector._baselines["test"]) <= 5

    def test_extract_features(self, detector):
        features = detector._extract_features({
            "auth_time_hour": 14,
            "day_of_week": 3,
            "nas_ip": "10.0.0.1",
            "eap_type": "PEAP",
            "username": "alice",
            "endpoint_mac": "AA:BB:CC:DD:EE:FF",
        })
        assert features["hour"] == 14
        assert features["day_of_week"] == 3
        assert features["nas_ip"] == "10.0.0.1"
        assert features["eap_type"] == "PEAP"

    def test_extract_features_defaults(self, detector):
        features = detector._extract_features({})
        assert "hour" in features
        assert features["day_of_week"] == 0


class TestPolicyDriftDetector:
    @pytest.fixture
    def drift_detector(self):
        return PolicyDriftDetector()

    @pytest.mark.asyncio
    async def test_no_drift(self, drift_detector):
        """All matching outcomes should show no drift"""
        with patch("app.anomaly._get_redis", new_callable=AsyncMock, return_value=None):
            for _ in range(10):
                await drift_detector.record_outcome("pol-1", "permit", "permit", True, 100)
            result = await drift_detector.analyze_drift("pol-1")
        assert result["overall_drift"] == "none"
        assert result["results"][0]["drift_percentage"] == 0.0

    @pytest.mark.asyncio
    async def test_high_drift(self, drift_detector):
        """Many mismatches should show high/critical drift"""
        with patch("app.anomaly._get_redis", new_callable=AsyncMock, return_value=None):
            for _ in range(8):
                await drift_detector.record_outcome("pol-2", "permit", "permit", True, 100)
            for _ in range(5):
                await drift_detector.record_outcome("pol-2", "permit", "deny", False, 100)
            result = await drift_detector.analyze_drift("pol-2")
        assert result["results"][0]["drift_percentage"] > 30
        assert result["overall_drift"] in ("high", "critical")

    @pytest.mark.asyncio
    async def test_analyze_all_policies(self, drift_detector):
        """Analyze drift across all recorded policies"""
        with patch("app.anomaly._get_redis", new_callable=AsyncMock, return_value=None):
            await drift_detector.record_outcome("pol-a", "permit", "permit", True, 50)
            await drift_detector.record_outcome("pol-b", "deny", "permit", False, 75)
            result = await drift_detector.analyze_drift()
        assert result["policies_analyzed"] == 2

    @pytest.mark.asyncio
    async def test_empty_policy(self, drift_detector):
        result = await drift_detector.analyze_drift("nonexistent")
        assert result["overall_drift"] == "none"
        assert result["policies_analyzed"] == 0

    @pytest.mark.asyncio
    async def test_window_cap(self, drift_detector):
        """Outcomes should be capped at _max_window"""
        drift_detector._max_window = 5
        with patch("app.anomaly._get_redis", new_callable=AsyncMock, return_value=None):
            for _ in range(10):
                await drift_detector.record_outcome("pol-cap", "permit", "permit", True, 100)
        assert len(drift_detector._policy_outcomes["pol-cap"]) <= 5
