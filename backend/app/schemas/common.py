"""
=============================================================================
Common Pydantic Schemas — pagination, health, error responses
=============================================================================
"""
from typing import Any, TypeVar

from pydantic import BaseModel, Field

from app.config import settings

T = TypeVar("T")


class HealthResponse(BaseModel):
    """Health check response."""
    status: str = "healthy"
    version: str = settings.APP_VERSION
    environment: str = settings.APP_ENV


class ErrorDetail(BaseModel):
    """Error detail payload."""
    code: str
    message: str
    details: dict[str, Any] | None = None


class ErrorResponse(BaseModel):
    """Standard error response."""
    status: str = "error"
    error: ErrorDetail


class PaginationParams(BaseModel):
    """Pagination query parameters."""
    page: int = Field(default=1, ge=1, description="Page number (1-indexed)")
    page_size: int = Field(default=20, ge=1, le=100, description="Items per page")


class PaginationResponse(BaseModel):
    """Pagination metadata in response."""
    total: int
    page: int
    page_size: int
    pages: int
