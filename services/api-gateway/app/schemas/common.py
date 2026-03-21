"""Common response schemas shared across all routers."""
from datetime import datetime
from typing import Any, Generic, List, Optional, TypeVar
from pydantic import BaseModel, Field
from uuid import UUID

T = TypeVar("T")


class ErrorResponse(BaseModel):
    detail: str
    error_code: Optional[str] = None


class MessageResponse(BaseModel):
    message: str
    status: str = "ok"


class PaginatedResponse(BaseModel, Generic[T]):
    items: List[Any] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 50
    has_more: bool = False


class HealthResponse(BaseModel):
    status: str
    service: str
    version: str = "1.0.0"
    uptime_seconds: Optional[float] = None


class HealthFullResponse(HealthResponse):
    database: str = "unknown"
    redis: str = "unknown"
    nats: str = "unknown"
    db_pool: Optional[dict] = None


class DiagnosticsResponse(BaseModel):
    overall: str
    checks: List[dict] = Field(default_factory=list)


class MetricsResponse(BaseModel):
    content_type: str = "text/plain"
