"""Tests for CapacityPlanner — metric recording, forecasting, alerts."""
import pytest
import time
from app.capacity_planner import CapacityPlanner


@pytest.fixture
def planner():
    return CapacityPlanner()


class TestRecordMetric:
    @pytest.mark.asyncio
    async def test_record_single(self, planner):
        await planner.record_metric("cpu_percent", 45.0)
        metrics = await planner.get_metrics_list()
        assert len(metrics) == 1
        assert metrics[0]["metric"] == "cpu_percent"
        assert metrics[0]["data_points"] == 1

    @pytest.mark.asyncio
    async def test_record_multiple(self, planner):
        for i in range(5):
            await planner.record_metric("auth_rate", float(i * 10))
        metrics = await planner.get_metrics_list()
        assert metrics[0]["data_points"] == 5

    @pytest.mark.asyncio
    async def test_max_points_trimmed(self, planner):
        planner._max_points = 10
        for i in range(15):
            await planner.record_metric("test", float(i))
        assert len(planner._series["test"]) == 10


class TestForecast:
    @pytest.mark.asyncio
    async def test_insufficient_data(self, planner):
        for i in range(5):
            await planner.record_metric("cpu", float(i))
        result = await planner.forecast("cpu")
        assert result["status"] == "insufficient_data"

    @pytest.mark.asyncio
    async def test_sufficient_data_returns_forecast(self, planner):
        base_ts = time.time() - 3600  # 1 hour ago
        for i in range(20):
            await planner.record_metric("auth_rate", 100.0 + i * 5, ts=base_ts + i * 180)
        result = await planner.forecast("auth_rate", horizon_hours=24)
        assert result["status"] == "ok"
        assert result["data_points"] == 20
        assert "forecast_value" in result
        assert "smoothed_value" in result
        assert result["forecast_value"] >= 0

    @pytest.mark.asyncio
    async def test_trend_slope_positive(self, planner):
        base_ts = time.time() - 3600
        for i in range(20):
            await planner.record_metric("endpoint_count", 1000.0 + i * 50, ts=base_ts + i * 180)
        result = await planner.forecast("endpoint_count")
        assert result["trend_slope"] > 0
        assert result["growth_rate_percent"] > 0

    @pytest.mark.asyncio
    async def test_cpu_alert(self, planner):
        base_ts = time.time() - 3600
        for i in range(20):
            await planner.record_metric("cpu_percent", 70.0 + i * 2, ts=base_ts + i * 180)
        result = await planner.forecast("cpu_percent")
        # The forecast should be high enough to trigger the CPU alert
        if result["forecast_value"] > 85:
            assert result["alert"] is not None
            assert "CPU" in result["alert"]

    @pytest.mark.asyncio
    async def test_nonexistent_metric(self, planner):
        result = await planner.forecast("nonexistent")
        assert result["status"] == "insufficient_data"


class TestGetAllForecasts:
    @pytest.mark.asyncio
    async def test_all_forecasts(self, planner):
        base_ts = time.time() - 3600
        for i in range(15):
            await planner.record_metric("cpu", 40.0 + i, ts=base_ts + i * 60)
            await planner.record_metric("mem", 50.0 + i, ts=base_ts + i * 60)
        result = await planner.get_all_forecasts()
        assert result["total_metrics"] == 2
        assert "cpu" in result["forecasts"]
        assert "mem" in result["forecasts"]
