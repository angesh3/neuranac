"""OpenTelemetry tracing middleware (G35).

Instruments incoming HTTP requests with OTEL spans. Exports traces to an
OTLP collector when ``OTEL_EXPORTER_OTLP_ENDPOINT`` is set; otherwise
traces are silently discarded (noop).
"""
import os
import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

logger = structlog.get_logger()

_tracer = None


def _init_tracer():
    global _tracer
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    service_name = os.getenv("OTEL_SERVICE_NAME", "neuranac-api-gateway")

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.resources import Resource

        resource = Resource.create({"service.name": service_name})
        provider = TracerProvider(resource=resource)

        if endpoint:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
            from opentelemetry.sdk.trace.export import BatchSpanProcessor
            exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
            provider.add_span_processor(BatchSpanProcessor(exporter))
            logger.info("OTEL tracing enabled", endpoint=endpoint, service=service_name)
        else:
            logger.debug("OTEL tracing disabled (no OTEL_EXPORTER_OTLP_ENDPOINT)")

        trace.set_tracer_provider(provider)
        _tracer = trace.get_tracer(service_name)
    except ImportError:
        logger.debug("opentelemetry SDK not installed — tracing disabled")
        _tracer = None
    except Exception as exc:
        logger.warning("OTEL init failed", error=str(exc))
        _tracer = None


# Initialise once at import time
_init_tracer()


class OTelTracingMiddleware(BaseHTTPMiddleware):
    """Adds an OTEL span around every HTTP request."""

    async def dispatch(self, request: Request, call_next):
        if _tracer is None:
            return await call_next(request)

        span_name = f"{request.method} {request.url.path}"
        with _tracer.start_as_current_span(span_name) as span:
            span.set_attribute("http.method", request.method)
            span.set_attribute("http.url", str(request.url))
            span.set_attribute("http.route", request.url.path)
            if request.headers.get("x-request-id"):
                span.set_attribute("http.request_id", request.headers["x-request-id"])

            response = await call_next(request)

            span.set_attribute("http.status_code", response.status_code)
            if response.status_code >= 400:
                span.set_attribute("error", True)
            return response
