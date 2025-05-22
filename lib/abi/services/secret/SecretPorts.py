from abc import ABC, abstractmethod
from typing import Any


class ISecretAdapter(ABC):
    @abstractmethod
    def get(self, key: str, default: Any = None) -> str | None:
        raise NotImplementedError()


class ISecretService(ABC):
    __adapter: ISecretAdapter

    @abstractmethod
    def get(self, key: str, default: Any = None) -> str | None:
        raise NotImplementedError()
