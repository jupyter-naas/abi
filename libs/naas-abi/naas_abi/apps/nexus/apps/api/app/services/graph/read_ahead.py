"""Read a slow consumer's stream ahead into a temporary file."""

from __future__ import annotations

import asyncio
import os
import tempfile
from collections.abc import AsyncIterator

CHUNK_BYTES = 64 * 1024


async def read_ahead(chunks: AsyncIterator[bytes]) -> AsyncIterator[bytes]:
    """``chunks`` read ahead into a temporary file at their own pace, served at
    the reader's: a slow HTTP client never stalls the source (a NATS transfer
    session expires after 60 s idle). Memory holds one chunk; a source error
    reaches the reader after the data before it; leaving early stops the
    source."""
    spool = tempfile.TemporaryFile(buffering=0)  # pread must see every write
    written, done, more = 0, False, asyncio.Event()
    failure: Exception | None = None

    async def fill() -> None:
        nonlocal written, done, failure
        try:
            async for chunk in chunks:
                await asyncio.to_thread(spool.write, chunk)
                written += len(chunk)
                more.set()
        except Exception as exc:  # noqa: BLE001 - delivered to the reader
            failure = exc
        finally:
            done = True
            more.set()

    filling = asyncio.create_task(fill())
    read = 0
    try:
        while True:
            if read < written:
                size = min(written - read, CHUNK_BYTES)
                data = await asyncio.to_thread(os.pread, spool.fileno(), size, read)
                if not data:
                    raise OSError("read-ahead file is shorter than what was written")
                read += len(data)
                yield data
                continue
            if done:
                if failure is not None:
                    raise failure
                return
            more.clear()
            await more.wait()
    finally:
        filling.cancel()
        await asyncio.gather(filling, return_exceptions=True)
        await chunks.aclose()  # type: ignore[attr-defined]
        spool.close()
