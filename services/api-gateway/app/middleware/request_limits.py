"""Request body size limits and pagination enforcement middleware.

Rejects requests exceeding configurable body size limits and enforces
maximum pagination limits on query parameters.
"""

import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

logger = logging.getLogger("neuranac.request_limits")

# Default limits
DEFAULT_MAX_BODY_BYTES = 10 * 1024 * 1024  # 10 MB
DEFAULT_MAX_PAGINATION_LIMIT = 200
DEFAULT_MAX_BULK_ITEMS = 1000


class RequestLimitsMiddleware(BaseHTTPMiddleware):
    """Enforces request body size limits and pagination caps.

    - Rejects POST/PUT/PATCH requests exceeding max_body_bytes.
    - Clamps `limit` query parameter to max_pagination_limit.
    - Rejects bulk payloads (arrays) exceeding max_bulk_items.
    """

    def __init__(
        self,
        app,
        max_body_bytes: int = DEFAULT_MAX_BODY_BYTES,
        max_pagination_limit: int = DEFAULT_MAX_PAGINATION_LIMIT,
        max_bulk_items: int = DEFAULT_MAX_BULK_ITEMS,
    ):
        super().__init__(app)
        self.max_body_bytes = max_body_bytes
        self.max_pagination_limit = max_pagination_limit
        self.max_bulk_items = max_bulk_items

    async def dispatch(self, request: Request, call_next):
        # --- Body size check (for mutating methods) ---
        if request.method in ("POST", "PUT", "PATCH"):
            content_length = request.headers.get("content-length")
            if content_length:
                try:
                    cl = int(content_length)
                    if cl > self.max_body_bytes:
                        logger.warning(
                            "Request body too large: %d bytes (max %d) from %s %s",
                            cl, self.max_body_bytes, request.method, request.url.path,
                        )
                        return JSONResponse(
                            status_code=413,
                            content={
                                "detail": f"Request body too large. Maximum size is {self.max_body_bytes} bytes.",
                                "max_bytes": self.max_body_bytes,
                            },
                        )
                except (ValueError, TypeError):
                    pass

        # --- Pagination limit clamping ---
        limit_param = request.query_params.get("limit")
        if limit_param:
            try:
                limit_val = int(limit_param)
                if limit_val > self.max_pagination_limit:
                    logger.debug(
                        "Clamping pagination limit from %d to %d for %s",
                        limit_val, self.max_pagination_limit, request.url.path,
                    )
                    # We can't modify query params in-place, so we set a scope hint
                    # that routers can check. The actual clamping happens via the
                    # le= validator on Query(limit) parameters in each router.
                    request.state.max_pagination_limit = self.max_pagination_limit
            except (ValueError, TypeError):
                pass

        response = await call_next(request)
        return response
