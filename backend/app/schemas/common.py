from datetime import UTC, datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


def _utcnow_iso() -> str:
    return datetime.now(UTC).isoformat()


class Response(BaseModel, Generic[T]):
    code: int = 0
    message: str = "ok"
    data: T | None = None
    timestamp: str = Field(default_factory=_utcnow_iso)


class PageResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
    total_pages: int

    @classmethod
    def create(cls, items: list[T], total: int, page: int, page_size: int) -> "PageResponse[T]":
        total_pages = (total + page_size - 1) // page_size
        return cls(
            items=items, total=total, page=page, page_size=page_size, total_pages=total_pages
        )


class ErrorResponse(BaseModel):
    code: int
    message: str
    data: Any = None
    timestamp: str = Field(default_factory=_utcnow_iso)


class IdempotencyKey(BaseModel):
    key: str = Field(..., min_length=36, max_length=36, pattern=r"^[0-9a-f-]{36}$")
