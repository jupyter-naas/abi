from abc import ABC, abstractmethod
from contextlib import contextmanager
from datetime import datetime
from queue import Queue
from typing import BinaryIO, Iterator, Optional

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
    @contextmanager
    def get_object_stream(self, prefix: str, key: str) -> Iterator[BinaryIO]:
        """Open *prefix/key* as a binary stream for incremental reads.

        Returns a context manager yielding a file-like object that supports
        ``read(n)``/iteration. Use this instead of :meth:`get_object` when
        the object may not fit in memory — e.g. multi-gigabyte JSON dumps
        consumed by streaming parsers. The implementation MUST release the
        underlying resource (file handle, HTTP body) on context exit.
        """
        ...  # pragma: no cover — abstract

    @abstractmethod
    def put_object(self, prefix: str, key: str, content: bytes) -> None:
        pass

    @abstractmethod
    def put_object_stream(self, prefix: str, key: str, stream: BinaryIO) -> None:
        """Write *prefix/key* by streaming from ``stream`` (a readable binary
        file-like). Use instead of :meth:`put_object` when the payload may not
        fit in memory — the implementation MUST NOT read the whole stream at once.
        """
        ...  # pragma: no cover — abstract

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
    @contextmanager
    def get_object_stream(self, prefix: str, key: str) -> Iterator[BinaryIO]:
        """Domain-side mirror of :meth:`IObjectStorageAdapter.get_object_stream`.

        See that method for the streaming-read contract.
        """
        ...  # pragma: no cover — abstract

    @abstractmethod
    def put_object(self, prefix: str, key: str, content: bytes) -> None:
        pass

    @abstractmethod
    def put_object_stream(self, prefix: str, key: str, stream: BinaryIO) -> None:
        """Write *prefix/key* by streaming from ``stream`` (a readable binary
        file-like). Use instead of :meth:`put_object` when the payload may not
        fit in memory — the implementation MUST NOT read the whole stream at once.
        """
        ...  # pragma: no cover — abstract

    @abstractmethod
    def delete_object(self, prefix: str, key: str) -> None:
        pass

    @abstractmethod
    def list_objects(self, prefix: str, queue: Optional[Queue] = None) -> list[str]:
        pass

    @abstractmethod
    def get_object_metadata(self, prefix: str, key: str) -> ObjectMetaData:
        pass
