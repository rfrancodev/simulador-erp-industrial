"""Shared Pydantic schemas and helpers used across domains."""

from typing import Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    """Standard pagination envelope for list endpoints (M-13)."""

    items: list[T]
    total: int
    page: int
    page_size: int


def paginate(items: list[T], total: int, skip: int, limit: int) -> PaginatedResponse[T]:
    """Build a PaginatedResponse from raw query results (L-19)."""
    return PaginatedResponse(
        items=items,
        total=total,
        page=skip // limit + 1 if limit > 0 else 1,
        page_size=limit,
    )