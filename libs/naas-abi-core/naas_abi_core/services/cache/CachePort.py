import datetime
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class CacheNotFoundError(Exception):
    pass


class CacheExpiredError(Exception):
    pass


class DataType(str, Enum):
    TEXT = "text"
    JSON = "json"
    BINARY = "binary"
    PICKLE = "pickle"


class CachedData(BaseModel):
    key: str
    data: Any
    data_type: DataType
    created_at: str = Field(default_factory=lambda: datetime.datetime.now(datetime.UTC).isoformat())


# Upper bound for one ``list_keys`` page (keeps NATS replies well under the payload limit).
MAX_KEYS_PER_PAGE = 1000


@dataclass(frozen=True)
class CacheKeyPage:
    """Cache keys in ascending order; ``next_after`` (the last key) continues."""

    keys: tuple[str, ...]
    next_after: str | None = None


@dataclass(frozen=True)
class CacheEntry:
    """A stored entry as is (never deserialized) and the tier holding it."""

    tier: str
    cached: CachedData


def check_page_limit(limit: int) -> None:
    if not 1 <= limit <= MAX_KEYS_PER_PAGE:
        raise ValueError(f"limit must be between 1 and {MAX_KEYS_PER_PAGE}, got {limit}")


def paginate_keys(
    keys: Iterable[str], prefix: str, limit: int, after: str | None
) -> CacheKeyPage:
    """One page of ``keys`` (any order, duplicates allowed). Cache adapters store
    entries under a hash of the key, so they enumerate everything and page here."""
    check_page_limit(limit)
    selected = sorted(
        {k for k in keys if k.startswith(prefix) and (after is None or k > after)}
    )
    page = tuple(selected[:limit])
    return CacheKeyPage(page, page[-1] if len(selected) > limit else None)


class ICacheAdapter:
    def get(self, key: str) -> CachedData:
        raise NotImplementedError("Not implemented")

    def set(self, key: str, value: CachedData) -> None:
        raise NotImplementedError("Not implemented")

    def set_if_absent(self, key: str, value: CachedData) -> bool:
        raise NotImplementedError("Not implemented")

    def delete(self, key: str) -> None:
        raise NotImplementedError("Not implemented")

    def exists(self, key: str) -> bool:
        raise NotImplementedError("Not implemented")

    def list_keys(
        self, prefix: str = "", *, limit: int = 100, after: str | None = None
    ) -> CacheKeyPage:
        """Keys (the logical keys, not their storage names) starting with
        ``prefix``, strictly after ``after``, ascending, at most ``limit``."""
        raise NotImplementedError("Not implemented")


class ICacheService:
    adapter: ICacheAdapter

    def __init__(self, adapter: ICacheAdapter):
        self.adapter = adapter

    def exists(self, key: str) -> bool:
        raise NotImplementedError("Not implemented")

    def delete(self, key: str) -> None:
        raise NotImplementedError("Not implemented")

    def get(self, key: str, ttl: datetime.timedelta | None = None) -> Any:
        raise NotImplementedError("Not implemented")

    def set_text(self, key: str, value: str) -> None:
        raise NotImplementedError("Not implemented")

    def set_json(self, key: str, value: dict) -> None:
        raise NotImplementedError("Not implemented")

    def set_binary(self, key: str, value: bytes) -> None:
        raise NotImplementedError("Not implemented")

    def set_pickle(self, key: str, value: Any) -> None:
        raise NotImplementedError("Not implemented")

    def set_json_if_absent(self, key: str, value: dict) -> bool:
        raise NotImplementedError("Not implemented")

    def set_binary_if_absent(self, key: str, value: bytes) -> bool:
        raise NotImplementedError("Not implemented")

    def list_keys(
        self, prefix: str = "", *, limit: int = 100, after: str | None = None
    ) -> CacheKeyPage:
        raise NotImplementedError("Not implemented")

    def get_entry(self, key: str) -> CacheEntry:
        raise NotImplementedError("Not implemented")
