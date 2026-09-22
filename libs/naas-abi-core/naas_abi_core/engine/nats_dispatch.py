"""Per-primary worker capacity for synchronous domains making nested NATS calls."""

import asyncio
import contextvars
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import TypeVar

Request = TypeVar("Request")
Response = TypeVar("Response")


class DomainRPCDispatcher:
    def __init__(self, name: str, max_workers: int = 8) -> None:
        self.name = name
        self.max_workers = max_workers
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
