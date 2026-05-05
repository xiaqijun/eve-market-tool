"""Shared Pydantic schemas: pagination, error responses."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PaginationParams(BaseModel):
    """Standard pagination query parameters."""

    page: int = Field(default=1, ge=1, description="Page number (1-indexed)")
    per_page: int = Field(default=50, ge=1, le=200, description="Items per page")


class PaginatedResponse(BaseModel):
    """Standard paginated response wrapper."""

    page: int
    per_page: int
    total: int
    pages: int
    items: list


class ErrorResponse(BaseModel):
    """Standard API error response."""

    detail: str
