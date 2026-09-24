"""Caller-owned chunk transfers. No retries or implicit operation replay."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from naas_abi_proto.transfer.v1 import transfer_pb2 as pb


def transfer_subject(prefix: str, operation: str, transfer_id: str = "") -> str:
    owner, separator, _ = transfer_id.partition(":")
    if separator:
        if len(owner) != 32 or any(c not in "0123456789abcdef" for c in owner):
            raise ValueError("Invalid transfer owner")
        return f"{prefix}.{owner}.{operation}"
    return f"{prefix}.{operation}"


class Transfer:
    def __init__(self, call, prefix, id, chunk_bytes):
        self.call, self.prefix, self.id, self.chunk_bytes = (
            call,
            prefix,
            id,
            chunk_bytes,
        )
        self.write_sequence = self.read_sequence = 0

    async def write(self, data: bytes) -> None:
        for offset in range(0, len(data), self.chunk_bytes):
            await self.call(
                transfer_subject(self.prefix, "write", self.id),
                pb.WriteRequest(
                    id=self.id,
                    sequence=self.write_sequence,
                    data=data[offset : offset + self.chunk_bytes],
                ),
                pb.WriteResponse,
            )
            self.write_sequence += 1

    async def start(self) -> None:
        await self.call(
            transfer_subject(self.prefix, "start", self.id),
            pb.StartRequest(id=self.id),
            pb.StartResponse,
        )

    async def fragments(self):
        while True:
            result = await self.call(
                transfer_subject(self.prefix, "read", self.id),
                pb.ReadRequest(id=self.id, sequence=self.read_sequence),
                pb.ReadResponse,
            )
            if result.sequence != self.read_sequence:
                raise ValueError("Transfer sequence mismatch")
            if result.done:
                return
            if result.pending:
                await asyncio.sleep(0.02)
                continue
            self.read_sequence += 1
            yield result.data, result.frame_end

    async def frames(self):
        frame = bytearray()
        async for data, end in self.fragments():
            frame.extend(data)
            if end:
                yield bytes(frame)
                frame.clear()
        if frame:
            raise ValueError("Incomplete transfer frame")


@asynccontextmanager
async def open_transfer(transport, prefix: str, operation: str, metadata: bytes = b""):
    nc = await transport.connect()
    size = min(64 * 1024, nc.max_payload // 2)
    opened = await transport.call(
        f"{prefix}.open",
        pb.OpenRequest(operation=operation, metadata=metadata, chunk_bytes=size),
        pb.OpenResponse,
    )
    transfer = Transfer(transport.call, prefix, opened.id, opened.chunk_bytes)
    try:
        yield transfer
    finally:
        try:
            await transport.call(
                transfer_subject(prefix, "close", opened.id),
                pb.CloseRequest(id=opened.id),
                pb.CloseResponse,
            )
        except Exception:  # cleanup cannot replace the original operation error
            logging.getLogger(__name__).warning(
                "Could not close transfer; server idle expiry applies", exc_info=True
            )


async def model_frames(client, operation, request):
    async with open_transfer(
        client._transport, "abi.svc.model_registry.v1.transfer", operation
    ) as transfer:
        await transfer.write(request.SerializeToString())
        await transfer.start()
        async for frame in transfer.frames():
            yield frame


class AsyncObjectReader:
    def __init__(self, transfer):
        self.iterator = transfer.fragments().__aiter__()
        self.buffer = bytearray()
        self.done = False

    async def read(self, size: int = -1) -> bytes:
        while not self.done and (size < 0 or len(self.buffer) < size):
            try:
                data, _ = await self.iterator.__anext__()
                self.buffer.extend(data)
            except StopAsyncIteration:
                self.done = True
        count = len(self.buffer) if size < 0 else size
        result = bytes(self.buffer[:count])
        del self.buffer[:count]
        return result

    def __aiter__(self):
        return self

    async def __anext__(self):
        data = await self.read(64 * 1024)
        if not data:
            raise StopAsyncIteration
        return data
