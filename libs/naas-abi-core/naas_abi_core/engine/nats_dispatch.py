"""Per-primary worker capacity for synchronous domains making nested NATS calls.

A kernel service handles up to ``max_concurrent_requests()`` calls at once
(``nats.max_concurrent_requests``, 64 by default): its endpoints admit that many
(``nats_tracing.ConcurrentRequests``), and its dispatcher has as many worker
threads, so an admitted call never waits for a thread.
"""

import asyncio
import contextvars
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import TypeVar

Request = TypeVar("Request")
Response = TypeVar("Response")

DEFAULT_MAX_CONCURRENT_REQUESTS = 64

_max_concurrent_requests = DEFAULT_MAX_CONCURRENT_REQUESTS


def configure(max_concurrent_requests: int) -> None:
    """Set how many calls each kernel service this process starts next handles at once."""
    global _max_concurrent_requests
    if max_concurrent_requests < 1:
        raise ValueError("A kernel service must handle at least one call at once")
    _max_concurrent_requests = max_concurrent_requests


def max_concurrent_requests() -> int:
    """How many calls a kernel service started now handles at once."""
    return _max_concurrent_requests


class DomainRPCDispatcher:
    def __init__(self, name: str, max_workers: int | None = None) -> None:
        self.name = name
        self.max_workers = (
            max_concurrent_requests() if max_workers is None else max_workers
        )
        self._executor: ThreadPoolExecutor | None = None

    async def call(
        self, function: Callable[[Request], Response], request: Request
    ) -> Response:
        # Called only on the primary's event loop. A distinct pool per primary
        # prevents waiting parents from consuming their dependencies' capacity.
        if self._executor is None:
            self._executor = ThreadPoolExecutor(
                max_workers=self.max_workers, thread_name_prefix=f"nats-{self.name}"
            )
        context = contextvars.copy_context()
        return await asyncio.get_running_loop().run_in_executor(
            self._executor, context.run, function, request
        )

    def close(self) -> None:
        executor, self._executor = self._executor, None
        if executor is not None:
            # Service.stop drains subscriptions first; never block the NATS loop.
            executor.shutdown(wait=False, cancel_futures=True)
