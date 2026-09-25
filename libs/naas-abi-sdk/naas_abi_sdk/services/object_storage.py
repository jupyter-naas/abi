from __future__ import annotations

import asyncio
from contextlib import AsyncExitStack, asynccontextmanager
from io import BytesIO
from queue import Queue
from typing import BinaryIO

from naas_abi_proto.object_storage.v1 import object_storage_pb2 as pb
from nats.errors import NoRespondersError

from naas_abi_sdk.services._codec import ServiceProxy
from naas_abi_sdk.services.errors import domain_error
from naas_abi_sdk.services.models import ObjectMetaData
from naas_abi_sdk.transfer import AsyncObjectReader, open_transfer, read_legacy_upload
from naas_abi_sdk.transport import RPCError


class ObjectStorageService(ServiceProxy):
    domain = "object_storage"

    async def get_object(self, prefix: str, key: str) -> bytes:
        async with self.get_object_stream(prefix, key) as stream:
            return await stream.read()

    async def put_object(self, prefix: str, key: str, content: bytes) -> None:
        nc = await self._client._transport.connect()
        if len(content) <= min(64 * 1024, nc.max_payload // 2):
            await self._request("put_object", prefix=prefix, key=key, content=content)
        else:
            await self.put_object_stream(prefix, key, BytesIO(content))

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

    @asynccontextmanager
    async def get_object_stream(self, prefix: str, key: str):
        metadata = pb.GetObjectRequest(prefix=prefix, key=key).SerializeToString()
        try:
            async with AsyncExitStack() as stack:
                try:
                    transfer = await stack.enter_async_context(
                        open_transfer(
                            self._client._transport,
                            "abi.svc.object_storage.v1.transfer",
                            "get",
                            metadata,
                        )
                    )
                except NoRespondersError:
                    content = await self._request("get_object", prefix=prefix, key=key)
                    yield _LegacyReader(content)
                    return
                await transfer.start()
                reader = AsyncObjectReader(transfer)
                await reader.prime()
                yield reader
        except RPCError as exc:
            raise domain_error(exc) from exc

    async def put_object_stream(self, prefix: str, key: str, stream: BinaryIO) -> None:
        metadata = pb.GetObjectRequest(prefix=prefix, key=key).SerializeToString()
        try:
            async with AsyncExitStack() as stack:
                try:
                    transfer = await stack.enter_async_context(
                        open_transfer(
                            self._client._transport,
                            "abi.svc.object_storage.v1.transfer",
                            "put",
                            metadata,
                        )
                    )
                except NoRespondersError:
                    nc = await self._client._transport.connect()
                    limit = min(nc.max_payload, 8 * 1024 * 1024)
                    content = await asyncio.to_thread(read_legacy_upload, stream, limit)
                    await self._request(
                        "put_object", prefix=prefix, key=key, content=content
                    )
                    return
                while chunk := await asyncio.to_thread(
                    stream.read, transfer.chunk_bytes
                ):
                    await transfer.write(chunk)
                await transfer.start()
                async for _ in transfer.fragments():
                    pass
        except RPCError as exc:
            raise domain_error(exc) from exc


class _LegacyReader:
    def __init__(self, content):
        self.stream = BytesIO(content)

    async def read(self, size=-1):
        return self.stream.read(size)

    def __aiter__(self):
        return self

    async def __anext__(self):
        data = await self.read(64 * 1024)
        if not data:
            raise StopAsyncIteration
        return data
