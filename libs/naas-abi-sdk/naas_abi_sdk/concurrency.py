"""Run a subscription's messages side by side, a bounded number at once.

nats-py hands a subscription its next message only once the callback for the
previous one has returned, so a handler awaited there answers one request at a
time. ``ConcurrentCalls.callback`` runs each message in its own task instead.
With ``limit`` calls running, the callback waits for a free slot, and later
messages stay in the subscription's buffer (nats-py's pending limits), each
until its caller's deadline.

Core's kernel services (``naas_abi_core.engine.nats_tracing``) and discovery,
and the SDK's agent and model hosts, use it.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_LIMIT = 64

Callback = Callable[[Any], Awaitable[None]]


class ConcurrentCalls:
    def __init__(self, limit: int = DEFAULT_LIMIT) -> None:
        if limit < 1:
            raise ValueError("At least one call must run at once")
        self.limit = limit
        # Calls received and not finished yet, including those waiting for a slot.
        self.in_flight = 0
        self._slots = asyncio.Semaphore(limit)
        self._tasks: set[asyncio.Task[None]] = set()
        self._idle = asyncio.Event()
        self._idle.set()

    def callback(self, cb: Callback) -> Callback:
        """``cb`` as a subscription callback: each message runs in its own task."""

        async def receive(msg: Any) -> None:
            # Counted at once: idle() waits for a call still waiting for a slot.
            self._started()
            try:
                await self._slots.acquire()
            except BaseException:
                self._finished()
                raise
            task = asyncio.create_task(self._run(cb, msg))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)

        return receive

    async def _run(self, cb: Callback, msg: Any) -> None:
        try:
            await cb(msg)
        except Exception:
            logger.warning(
                "NATS call on %s failed", getattr(msg, "subject", "?"), exc_info=True
            )
        finally:
            self._slots.release()
            self._finished()

    def _started(self) -> None:
        self.in_flight += 1
        self._idle.clear()

    def _finished(self) -> None:
        self.in_flight -= 1
        if not self.in_flight:
            self._idle.set()

    async def idle(self) -> None:
        """Return once every call received so far has finished."""
        await self._idle.wait()

    async def cancel(self) -> None:
        """Cancel the calls still running."""
        tasks = list(self._tasks)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
