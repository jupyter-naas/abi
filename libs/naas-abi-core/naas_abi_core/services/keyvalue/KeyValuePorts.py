from abc import ABC, abstractmethod


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
