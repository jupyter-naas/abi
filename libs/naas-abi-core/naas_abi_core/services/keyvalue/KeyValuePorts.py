from abc import ABC, abstractmethod
from collections.abc import Iterable
from dataclasses import dataclass

# Upper bound for one ``list_keys`` page (keeps NATS replies well under the payload limit).
MAX_KEYS_PER_PAGE = 1000


class KVNotFoundError(Exception):
    pass


class KVLockTimeoutError(Exception):
    """Raised when ``KeyValueService.lock`` cannot acquire the key in time."""

    def __init__(self, key: str, attempts: int, timeout: float) -> None:
        self.key = key
        self.attempts = attempts
        self.timeout = timeout
        super().__init__(
            f"Could not acquire lock for {key!r} after {timeout:g}s "
            f"({attempts} attempt{'s' if attempts != 1 else ''})"
        )


@dataclass(frozen=True)
class KVKeyPage:
    """Keys in ascending order; ``next_after`` (the last key) continues the listing."""

    keys: tuple[str, ...]
    next_after: str | None = None


def check_page_limit(limit: int) -> None:
    if not 1 <= limit <= MAX_KEYS_PER_PAGE:
        raise ValueError(
            f"limit must be between 1 and {MAX_KEYS_PER_PAGE}, got {limit}"
        )


def paginate_keys(
    keys: Iterable[str], prefix: str, limit: int, after: str | None
) -> KVKeyPage:
    """One page of ``keys`` (any order, duplicates allowed) for adapters that
    enumerate everything, e.g. Redis ``SCAN``."""
    check_page_limit(limit)
    selected = sorted(
        {k for k in keys if k.startswith(prefix) and (after is None or k > after)}
    )
    page = tuple(selected[:limit])
    return KVKeyPage(page, page[-1] if len(selected) > limit else None)


class IKeyValueAdapter(ABC):
    @abstractmethod
    def get(self, key: str) -> bytes:
        raise NotImplementedError()

    @abstractmethod
    def set(self, key: str, value: bytes, ttl: int | None = None) -> None:
        raise NotImplementedError()

    @abstractmethod
    def set_if_not_exists(
        self,
        key: str,
        value: bytes,
        ttl: int | None = None,
    ) -> bool:
        raise NotImplementedError()

    @abstractmethod
    def delete(self, key: str) -> None:
        raise NotImplementedError()

    @abstractmethod
    def delete_if_value_matches(self, key: str, value: bytes) -> bool:
        raise NotImplementedError()

    @abstractmethod
    def exists(self, key: str) -> bool:
        raise NotImplementedError()

    @abstractmethod
    def list_keys(
        self, prefix: str = "", *, limit: int = 100, after: str | None = None
    ) -> KVKeyPage:
        """Live (unexpired) keys starting with ``prefix``, strictly after ``after``,
        ascending, at most ``limit`` (1..MAX_KEYS_PER_PAGE)."""
        raise NotImplementedError()

    @abstractmethod
    def get_ttl(self, key: str) -> int | None:
        """Whole seconds before ``key`` expires (rounded up), ``None`` if it never
        does. Raises KVNotFoundError."""
        raise NotImplementedError()
