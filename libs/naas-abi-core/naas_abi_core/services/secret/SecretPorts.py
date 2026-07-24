from abc import ABC, abstractmethod
from typing import Any


class SecretAuthenticationError(Exception):
    pass


class ISecretAdapter(ABC):
    @abstractmethod
    def get(self, key: str, default: Any = None) -> str | Any | None:
        raise NotImplementedError()

    @abstractmethod
    def set(self, key: str, value: str):
        raise NotImplementedError()

    @abstractmethod
    def remove(self, key: str):
        raise NotImplementedError()

    @abstractmethod
    def list(self) -> dict[str, str | None]:
        raise NotImplementedError()


class ISecretService(ABC):
    __adapter: list[ISecretAdapter]

    @abstractmethod
    def get(self, key: str, default: Any = None) -> str | Any | None:
        raise NotImplementedError()

    @abstractmethod
    def set(self, key: str, value: str):
        raise NotImplementedError()

    @abstractmethod
    def remove(self, key: str):
        raise NotImplementedError()

    @abstractmethod
    def list(self) -> dict[str, str | None]:
        raise NotImplementedError()
        raise NotImplementedError()
