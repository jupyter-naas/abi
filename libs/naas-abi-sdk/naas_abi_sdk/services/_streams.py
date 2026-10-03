"""Read a domain's transfer/v1 stream (docs/adr/20261003_nats-streamed-results.md)."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from typing import Any

from nats.errors import NoRespondersError

from naas_abi_sdk.services.errors import domain_error
from naas_abi_sdk.transfer import open_transfer
from naas_abi_sdk.transport import RPCError


@asynccontextmanager
async def open_stream(
    client: Any, prefix: str, operation: str, metadata: bytes
) -> AsyncIterator[AsyncIterator[bytes] | None]:
    """Yield the stream's frames, fetched as they are iterated, or ``None`` when
    no host answers the open (an engine without it: use the unary call).
    Error replies raise the domain's exception; leaving closes the session."""
    async with AsyncExitStack() as stack:
        try:
            transfer = await stack.enter_async_context(
                open_transfer(client._transport, prefix, operation, metadata)
            )
            await transfer.start()
        except NoRespondersError:
            yield None
            return
        except RPCError as exc:
            raise domain_error(exc) from exc
        yield _mapping_errors(transfer.frames())


async def _mapping_errors(frames: AsyncIterator[bytes]) -> AsyncIterator[bytes]:
    try:
        async for frame in frames:
            yield frame
    except RPCError as exc:
        raise domain_error(exc) from exc


async def each(items: list) -> AsyncIterator[Any]:
    for item in items:
        yield item
