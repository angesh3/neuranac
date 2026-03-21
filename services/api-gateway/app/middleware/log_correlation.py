"""Structured log correlation middleware (G39).

Injects a request-scoped correlation ID into structlog context so every log
line emitted during a request carries the same ``request_id``, ``method``,
and ``path``.  Also sets the ``X-Request-ID`` response header.
"""
import uuid
from contextvars import ContextVar

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

_request_id_var: ContextVar[str] = ContextVar("request_id", default="")


def get_request_id() -> str:
    return _request_id_var.get()


class LogCorrelationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        req_id = request.headers.get("x-request-id") or str(uuid.uuid4())
        _request_id_var.set(req_id)

        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(
            request_id=req_id,
            method=request.method,
            path=request.url.path,
        )

        response = await call_next(request)
        response.headers["X-Request-ID"] = req_id
        structlog.contextvars.clear_contextvars()
        return response
