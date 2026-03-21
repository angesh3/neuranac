"""
Predictive Capacity Planning — forecasts RADIUS auth load, endpoint growth,
and resource utilization using exponential smoothing and linear regression.
"""
import time
import math
import structlog
from collections import defaultdict
from typing import Dict, Any, List, Optional

logger = structlog.get_logger()


class CapacityPlanner:
    """Forecasts capacity needs from historical metrics."""

    def __init__(self):
        # Time-series data: metric_name -> [(timestamp, value)]
        self._series: Dict[str, List[tuple]] = defaultdict(list)
        self._max_points = 10000

    async def record_metric(self, metric: str, value: float, ts: Optional[float] = None):
        """Record a capacity metric data point."""
        ts = ts or time.time()
        self._series[metric].append((ts, value))
        if len(self._series[metric]) > self._max_points:
            self._series[metric] = self._series[metric][-self._max_points:]

    async def forecast(self, metric: str, horizon_hours: int = 24) -> Dict[str, Any]:
        """Forecast a metric value N hours into the future."""
        data = self._series.get(metric, [])
        if len(data) < 10:
            return {
                "metric": metric,
                "status": "insufficient_data",
                "message": f"Need at least 10 data points, have {len(data)}",
                "current_value": data[-1][1] if data else None,
            }

        values = [v for _, v in data]
        timestamps = [t for t, _ in data]

        # Simple linear regression for trend
        n = len(values)
        x = list(range(n))
        x_mean = sum(x) / n
        y_mean = sum(values) / n
        ss_xy = sum((x[i] - x_mean) * (values[i] - y_mean) for i in range(n))
        ss_xx = sum((x[i] - x_mean) ** 2 for i in range(n))
        slope = ss_xy / ss_xx if ss_xx > 0 else 0
        intercept = y_mean - slope * x_mean

        # Forecast
        avg_interval = (timestamps[-1] - timestamps[0]) / max(n - 1, 1)
        steps_ahead = int(horizon_hours * 3600 / max(avg_interval, 1))
        forecast_value = intercept + slope * (n + steps_ahead)

        # Exponential smoothing for short-term
        alpha = 0.3
        smoothed = values[0]
        for v in values[1:]:
            smoothed = alpha * v + (1 - alpha) * smoothed

        # Growth rate
        if len(values) >= 2 and values[0] > 0:
            growth_rate = (values[-1] - values[0]) / values[0] * 100
        else:
            growth_rate = 0

        # Capacity alert
        alert = None
        if metric == "auth_rate_per_sec" and forecast_value > 5000:
            alert = "RADIUS auth rate may exceed 5000/sec — consider adding a RADIUS node"
        elif metric == "endpoint_count" and forecast_value > 100000:
            alert = "Endpoint count approaching 100K — review database indexing and caching"
        elif metric == "cpu_percent" and forecast_value > 85:
            alert = "CPU utilization forecast >85% — scale horizontally or vertically"
        elif metric == "memory_percent" and forecast_value > 90:
            alert = "Memory utilization forecast >90% — add RAM or optimize caching"
        elif metric == "disk_percent" and forecast_value > 80:
            alert = "Disk utilization forecast >80% — expand storage or enable retention policies"

        return {
            "metric": metric,
            "status": "ok",
            "data_points": n,
            "current_value": round(values[-1], 2),
            "smoothed_value": round(smoothed, 2),
            "forecast_value": round(max(0, forecast_value), 2),
            "forecast_horizon_hours": horizon_hours,
            "trend_slope": round(slope, 6),
            "growth_rate_percent": round(growth_rate, 2),
            "alert": alert,
        }

    async def get_all_forecasts(self, horizon_hours: int = 24) -> Dict[str, Any]:
        """Forecast all tracked metrics."""
        results = {}
        for metric in self._series:
            results[metric] = await self.forecast(metric, horizon_hours)
        alerts = [r.get("alert") for r in results.values() if r.get("alert")]
        return {
            "forecasts": results,
            "total_metrics": len(results),
            "alerts": alerts,
            "horizon_hours": horizon_hours,
        }

    async def get_metrics_list(self) -> List[Dict[str, Any]]:
        """List all tracked metrics with current values."""
        return [
            {
                "metric": name,
                "data_points": len(data),
                "current_value": round(data[-1][1], 2) if data else None,
                "oldest": data[0][0] if data else None,
                "newest": data[-1][0] if data else None,
            }
            for name, data in self._series.items()
        ]
