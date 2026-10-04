"""Read a domain's transfer/v1 stream (docs/adr/20261003_nats-streamed-results.md)."""

from __future__ import annotations

from collections.abc import AsyncIterable, AsyncIterator, Iterable
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Any

from nats.errors import NoRespondersError

from naas_abi_sdk.services.errors import domain_error
from naas_abi_sdk.transfer import open_transfer
from naas_abi_sdk.transport import RPCError


@asynccontextmanager
async def open_stream(
    client: Any,
    prefix: str,
    operation: str,
    metadata: bytes,
    upload: Iterable[bytes] | AsyncIterable[bytes] | None = None,
) -> AsyncIterator[AsyncIterator[bytes] | None]:
    """Yield the stream's frames, fetched as they are iterated, or ``None`` when
    no host answers the open (an engine without it: use the unary call).
    ``upload`` is sent first, read lazily in negotiated chunks. Error replies
    raise the domain's exception; leaving closes the session, which discards
    an unfinished upload."""
    async with AsyncExitStack() as stack:
        try:
            transfer = await stack.enter_async_context(
                open_transfer(client._transport, prefix, operation, metadata)
            )
            if upload is not None:
                async for chunk in _chunks(upload, transfer.chunk_bytes):
                    await transfer.write(chunk)
            await transfer.start()
        except NoRespondersError:
            yield None
            return
        except RPCError as exc:
            raise domain_error(exc) from exc
        yield _mapping_errors(transfer.frames())


async def _chunks(
    pieces: Iterable[bytes] | AsyncIterable[bytes], size: int
) -> AsyncIterator[bytes]:
    """``pieces`` regrouped into chunks of ``size`` bytes; memory holds one."""
    buffer = bytearray()

    async def pending() -> AsyncIterator[bytes]:
        while len(buffer) >= size:
            yield bytes(buffer[:size])
            del buffer[:size]

    if isinstance(pieces, AsyncIterable):
        async for piece in pieces:
            buffer.extend(piece)
            async for chunk in pending():
                yield chunk
    else:
        for piece in pieces:
            buffer.extend(piece)
            async for chunk in pending():
                yield chunk
    if buffer:
        yield bytes(buffer)


async def _mapping_errors(frames: AsyncIterator[bytes]) -> AsyncIterator[bytes]:
    try:
        async for frame in frames:
            yield frame
    except RPCError as exc:
        raise domain_error(exc) from exc


async def each(items: list) -> AsyncIterator[Any]:
    for item in items:
        yield item
