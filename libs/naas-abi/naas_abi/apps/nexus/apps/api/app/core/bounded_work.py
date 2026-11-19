"""Bounds on expensive work done for a request in the API process.

Office previews, archive extraction and sheet calculation each take seconds of
CPU, memory or a child process. One ``BoundedWork`` per kind runs the work off
the event loop, in at most ``concurrent`` threads at once for the whole
process, and lets one caller start at most ``per_user`` of them in
``window_seconds``. Past either bound the request gets 429 at once (with
``Retry-After``): nothing waits in line holding a thread.

A slot is held by the work itself, not by the request waiting for it: when the
request goes away (the client disconnects), the work still running keeps its
slot until it ends.
"""

from __future__ import annotations

import asyncio
import threading
import time
from collections import deque
from collections.abc import Callable
from typing import Any, TypeVar

from fastapi import HTTPException, status

T = TypeVar("T")


class BoundedWork:
    def __init__(
        self,
        name: str,
        *,
        concurrent: int,
        per_user: int,
        window_seconds: float = 60.0,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        if concurrent < 1 or per_user < 1 or window_seconds <= 0:
            raise ValueError("concurrent, per_user and window_seconds are positive")
        self.name = name
        self.concurrent = concurrent
        self.per_user = per_user
        self.window_seconds = window_seconds
        self._clock = clock
        self._slots = threading.BoundedSemaphore(concurrent)
        self._lock = threading.Lock()
        self._starts: dict[str, deque[float]] = {}

    def _refused(self, detail: str, retry_after: float) -> HTTPException:
        return HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=detail,
            headers={"Retry-After": str(max(1, int(retry_after + 0.999)))},
        )

    def _admit(self, caller: str) -> None:
        """Count one start for ``caller``; 429 past ``per_user`` in the window."""
        now = self._clock()
        with self._lock:
            starts = self._starts.setdefault(caller, deque())
            while starts and now - starts[0] >= self.window_seconds:
                starts.popleft()
            if len(starts) >= self.per_user:
                raise self._refused(
                    f"Too many {self.name} requests: try again shortly",
                    starts[0] + self.window_seconds - now,
                )
            starts.append(now)
            # Forget callers whose window is empty, so the map stays small.
            if len(self._starts) > 4096:
                stale = [
                    key
                    for key, seen in self._starts.items()
                    if not seen or now - seen[-1] >= self.window_seconds
                ]
                for key in stale:
                    self._starts.pop(key, None)

    async def run(self, caller: str, fn: Callable[..., T], /, *args: Any, **kwargs: Any) -> T:
        """Run ``fn`` in a worker thread, within both bounds. The call context
        (the signed-in user, for IAM) goes with it. A start is counted against
        the caller only once it has a slot."""
        if not self._slots.acquire(blocking=False):
            raise self._refused(f"The server is busy with {self.name}: try again shortly", 5)
        try:
            self._admit(caller)
        except BaseException:
            self._slots.release()
            raise

        guard = threading.Lock()
        state = {"started": False, "abandoned": False}

        def held() -> T | None:
            with guard:
                if state["abandoned"]:
                    return None
                state["started"] = True
            try:
                return fn(*args, **kwargs)
            finally:
                self._slots.release()  # by the work, whenever it ends

        try:
            return await asyncio.to_thread(held)  # type: ignore[return-value]
        except BaseException:
            # The work never started (cancelled while queued): its slot is freed
            # here, and it will not start later.
            with guard:
                if not state["started"]:
                    state["abandoned"] = True
                    self._slots.release()
            raise
