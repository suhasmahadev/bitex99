"""
Generic cursor-based and offset-based pagination utilities.
Matches SPEC.md Section 8 exactly.
"""

from __future__ import annotations

from typing import Any, Generic, Sequence, TypeVar

from pydantic import BaseModel, Field

from app.config import get_settings

settings = get_settings()

T = TypeVar("T")


class PaginationParams(BaseModel):
    """Query parameters for offset pagination."""
    page: int = Field(1, ge=1, description="Page number (1-indexed)")
    page_size: int = Field(
        settings.DEFAULT_PAGE_SIZE,
        ge=1,
        le=settings.MAX_PAGE_SIZE,
        description="Items per page",
    )

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        return self.page_size


class PaginationMeta(BaseModel):
    page: int
    limit: int
    total_items: int
    total_pages: int
    has_next: bool
    has_prev: bool


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard paginated response wrapper matching SPEC.md."""
    data: list[Any]  # will be overridden by concrete types
    pagination: PaginationMeta

    @classmethod
    def create(
        cls,
        items: Sequence[Any],
        total: int,
        params: PaginationParams,
    ) -> "PaginatedResponse":
        total_pages = max(1, (total + params.page_size - 1) // params.page_size)
        has_next = params.page < total_pages
        has_prev = params.page > 1

        meta = PaginationMeta(
            page=params.page,
            limit=params.page_size,
            total_items=total,
            total_pages=total_pages,
            has_next=has_next,
            has_prev=has_prev,
        )

        return cls(
            data=list(items),
            pagination=meta,
        )
