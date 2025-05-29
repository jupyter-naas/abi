from abc import ABC, abstractmethod
from typing import Any, Dict, List


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
    def list(self) -> Dict[str, str | None]:
        raise NotImplementedError()


class ISecretService(ABC):
    __adapter: List[ISecretAdapter]

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
    def list(self) -> Dict[str, str | None]:
        raise NotImplementedError()
