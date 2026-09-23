from __future__ import annotations

from queue import Queue
from typing import BinaryIO

from naas_abi_sdk.services._codec import ServiceProxy
from naas_abi_sdk.services.models import ObjectMetaData


class ObjectStorageService(ServiceProxy):
    domain = "object_storage"

    async def get_object(self, prefix: str, key: str) -> bytes:
        return await self._request("get_object", prefix=prefix, key=key)

    async def put_object(self, prefix: str, key: str, content: bytes) -> None:
        await self._request("put_object", prefix=prefix, key=key, content=content)

    async def delete_object(self, prefix: str, key: str) -> None:
        await self._request("delete_object", prefix=prefix, key=key)

    async def list_objects(
        self, prefix: str = "", queue: Queue | None = None
    ) -> list[str]:
        keys = await self._request("list_objects", prefix=prefix)
        if queue is not None:
            for key in keys:
                queue.put_nowait(key)
        return keys

    async def list_objects_recursive(
        self, prefix: str = "", queue: Queue | None = None
    ) -> list[str]:
        keys = await self._request("list_objects_recursive", prefix=prefix)
        if queue is not None:
            for key in keys:
                queue.put_nowait(key)
        return keys

    async def get_object_metadata(self, prefix: str, key: str) -> ObjectMetaData:
        return await self._request("get_object_metadata", prefix=prefix, key=key)

    async def get_object_stream(self, prefix: str, key: str):
        raise NotImplementedError("Object streaming has no remote contract yet")

    async def put_object_stream(self, prefix: str, key: str, stream: BinaryIO) -> None:
        raise NotImplementedError("Object streaming has no remote contract yet")
