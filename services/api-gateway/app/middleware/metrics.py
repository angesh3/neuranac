"""Prometheus metrics middleware - exports request/response metrics using prometheus_client"""
import time
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

# ── Counters ──────────────────────────────────────────────────────────────────
http_requests_total = Counter(
    "http_requests_total", "Total HTTP requests",
    ["method", "path", "status"],
)

http_request_duration = Histogram(
    "http_request_duration_seconds", "HTTP request duration in seconds",
    ["method", "path"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

auth_attempts_total = Counter("auth_attempts_total", "Total authentication attempts", ["result"])
policy_evaluations_total = Counter("policy_evaluations_total", "Total policy evaluations")
coa_sent_total = Counter("coa_sent_total", "Total CoA requests sent")
siem_events_forwarded = Counter("siem_events_forwarded", "Total SIEM events forwarded")

# ── Gauges ────────────────────────────────────────────────────────────────────
active_sessions = Gauge("active_sessions", "Currently active RADIUS sessions")


def _normalize_path(path: str) -> str:
    """Collapse UUID / numeric path segments to reduce cardinality."""
    parts = path.strip("/").split("/")
    normalized = []
    for p in parts:
        if len(p) == 36 and p.count("-") == 4:
            normalized.append("{id}")
        elif p.isdigit():
            normalized.append("{id}")
        else:
            normalized.append(p)
    return "/" + "/".join(normalized)


class PrometheusMetricsMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path == "/metrics":
            return await call_next(request)

        start = time.monotonic()
        response = await call_next(request)
        duration = time.monotonic() - start

        method = request.method
        path = _normalize_path(request.url.path)
        status_code = str(response.status_code)

        http_requests_total.labels(method=method, path=path, status=status_code).inc()
        http_request_duration.labels(method=method, path=path).observe(duration)

        # Track auth-specific metrics
        raw_path = request.url.path
        if "/auth" in raw_path:
            result = "success" if response.status_code == 200 else "failure"
            auth_attempts_total.labels(result=result).inc()
        if "/policies" in raw_path and method == "POST":
            policy_evaluations_total.inc()

        return response


def increment_metric(name: str, value: int = 1):
    """Increment a named counter metric (backwards-compatible helper)."""
    metric_map = {
        "coa_sent_total": coa_sent_total,
        "siem_events_forwarded": siem_events_forwarded,
        "policy_evaluations_total": policy_evaluations_total,
    }
    m = metric_map.get(name)
    if m:
        m.inc(value)
    elif name == "active_sessions":
        active_sessions.inc(value)


def get_metrics_text() -> str:
    """Export metrics in Prometheus text exposition format."""
    return generate_latest().decode("utf-8")
