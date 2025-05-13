from abc import ABC, abstractmethod
from queue import Queue
from typing import Optional


class Exceptions:
    class ObjectNotFound(Exception):
        pass

    class ObjectAlreadyExists(Exception):
        pass


class IObjectStorageAdapter(ABC):
    @abstractmethod
    def get_object(self, prefix: str, key: str) -> bytes:
        pass

    @abstractmethod
    def put_object(self, prefix: str, key: str, content: bytes) -> None:
        pass

    @abstractmethod
    def delete_object(self, prefix: str, key: str) -> None:
        pass

    @abstractmethod
    def list_objects(self, prefix: str, queue: Optional[Queue] = None) -> list[str]:
        pass


class IObjectStorageDomain(ABC):
    @abstractmethod
    def get_object(self, prefix: str, key: str) -> bytes:
        pass

    @abstractmethod
    def put_object(self, prefix: str, key: str, content: bytes) -> None:
        pass

    @abstractmethod
    def delete_object(self, prefix: str, key: str) -> None:
        pass

    @abstractmethod
    def list_objects(self, prefix: str, queue: Optional[Queue] = None) -> list[str]:
        pass
