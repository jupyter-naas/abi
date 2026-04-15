from abc import ABC, abstractmethod
from datetime import datetime
from queue import Queue
from typing import Optional

from pydantic import BaseModel


class Exceptions:
    class ObjectNotFound(Exception):
        pass

    class ObjectAlreadyExists(Exception):
        pass


class ObjectMetaData(BaseModel):
    file_path: str
    file_name: str
    file_size_bytes: int
    created_time: Optional[datetime]
    modified_time: Optional[datetime]
    accessed_time: Optional[datetime]
    permissions: Optional[str]
    mime_type: Optional[str]
    encoding: Optional[str]


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

    @abstractmethod
    def get_object_metadata(self, prefix: str, key: str) -> ObjectMetaData:
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

    @abstractmethod
    def get_object_metadata(self, prefix: str, key: str) -> ObjectMetaData:
        pass
