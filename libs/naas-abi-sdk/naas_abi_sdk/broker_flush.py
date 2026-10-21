"""Wait until the broker has processed what a NATS connection sent."""

from __future__ import annotations

import asyncio
from typing import Any


async def flush_to_broker(nc: Any, timeout: float = 10) -> None:
    """Return once the broker has processed what ``nc`` sent so far: its
    SUBs serve, its UNSUBs stop delivery, its PUBs are routed.

    ``Client.flush`` alone does not promise it: it writes its PING straight
    to the socket, ahead of the SUBs, UNSUBs and PUBs still buffered for the
    flusher task, so the PONG can come back first (seen on nats-server 2.14:
    a request right after a subscribe found no responder, or one that had
    left). Raises ``asyncio.TimeoutError`` after ``timeout`` seconds, and
    lets a cancellation of the caller through.

    Reaches into nats-py: ``Client._flush_pending``. A client without it
    (a fake, another nats-py) gets ``Client.flush`` alone.
    """
    flush_pending = getattr(nc, "_flush_pending", None)
    if flush_pending is not None:
        # On the socket. nats-py's ``_flush_pending`` swallows ``CancelledError``,
        # so ``wait_for`` would return instead of raising on timeout, and lose
        # a cancellation of the caller: it runs in a task of its own.
        flushing = asyncio.ensure_future(flush_pending(force_flush=True))
        try:
            done, _ = await asyncio.wait({flushing}, timeout=timeout)
        finally:
            if not flushing.done():  # timed out, or the caller was cancelled
                flushing.cancel()
        if not done:
            raise asyncio.TimeoutError("The broker connection did not flush in time")
        flushing.result()
    await nc.flush(timeout=timeout)  # ...and processed by the broker
