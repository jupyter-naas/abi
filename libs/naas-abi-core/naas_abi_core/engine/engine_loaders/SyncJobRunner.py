"""Run a sync job handler so that a timeout or cancel really stops it.

Each run gets its own thread (never a shared executor), so an interrupt can
only land in that run's code. On a timeout, a close or a cancel request:

1. ``ctx.cancelled`` is set: cooperative handlers stop by themselves;
2. after ``interrupt_grace_seconds``, ``JobInterrupted`` is raised inside the
   thread (``PyThreadState_SetAsyncExc``), at its next Python bytecode;
3. the runner returns only once the thread has exited, so the job's
   concurrency slot stays taken and its message stays in progress meanwhile.

An interrupt cannot break a blocking C call (e.g. a socket read without a
timeout); it fires when that call returns. ``interrupt_grace_seconds=None``
disables step 2.
"""

from __future__ import annotations

import asyncio
import contextlib
import ctypes
import threading
from collections.abc import Callable
from typing import Any


class JobInterrupted(BaseException):
    """Raised inside a sync job's thread when its run is timed out or cancelled.

    A ``BaseException`` so that ``except Exception`` in job code does not swallow it.
    """


def _set_async_exc(ident: int, exc: type[BaseException] | None) -> int:
    return ctypes.pythonapi.PyThreadState_SetAsyncExc(
        ctypes.c_ulong(ident), ctypes.py_object(exc) if exc is not None else None
    )


class _Thread:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.ident: int | None = None
        self.finished = False
        self.interrupted = False

    def interrupt(self) -> bool:
        with self.lock:
            if self.finished or self.interrupted or self.ident is None:
                return False
            self.interrupted = _set_async_exc(self.ident, JobInterrupted) == 1
            return self.interrupted

    def finish(self) -> None:
        with self.lock:
            self.finished = True
            if self.interrupted and self.ident is not None:
                _set_async_exc(self.ident, None)  # drop it if not delivered yet


class SyncJobRunner:
    def __init__(
        self, handler: Callable[[Any], Any], *, interrupt_grace_seconds: float | None
    ) -> None:
        self.handler = handler
        self.interrupt_grace_seconds = interrupt_grace_seconds

    async def __call__(self, ctx: Any) -> Any:
        loop = asyncio.get_running_loop()
        done: asyncio.Future[Any] = loop.create_future()
        state = _Thread()

        def resolve(outcome: tuple[bool, Any]) -> None:
            if done.done():
                return
            ok, value = outcome
            if ok:
                done.set_result(value)
            else:
                done.set_exception(value)

        def target() -> None:
            outcome: tuple[bool, Any]
            try:
                try:
                    with state.lock:
                        state.ident = threading.get_ident()
                    outcome = (True, self.handler(ctx))
                except BaseException as exc:  # noqa: BLE001 - handed to the awaiting task
                    outcome = (False, exc)
                finally:
                    state.finish()
            except JobInterrupted as exc:  # arrived after the handler returned
                state.finish()
                outcome = (False, exc)
            with contextlib.suppress(RuntimeError):  # loop closed on shutdown
                loop.call_soon_threadsafe(resolve, outcome)

        thread = threading.Thread(
            target=target, name=f"abi-job-{ctx.run_id}", daemon=True
        )
        thread.start()

        stopped_by_host = False
        cancel_request = asyncio.ensure_future(ctx.cancelled.wait())
        try:
            await asyncio.wait(
                {done, cancel_request}, return_when=asyncio.FIRST_COMPLETED
            )
        except asyncio.CancelledError:  # timeout or host close
            stopped_by_host = True
            ctx.cancelled.set()
        finally:
            cancel_request.cancel()
        if not done.done():
            await self._stop(state, done)
        if stopped_by_host:
            with contextlib.suppress(BaseException):
                done.result()
            raise asyncio.CancelledError
        return done.result()

    async def _stop(self, state: _Thread, done: asyncio.Future[Any]) -> None:
        """Wait out the grace period, interrupt, then wait for the thread to exit."""
        if self.interrupt_grace_seconds is not None:
            # A second cancel (a timeout, then the host's close) ends the grace early.
            with contextlib.suppress(asyncio.CancelledError):
                await asyncio.wait({done}, timeout=self.interrupt_grace_seconds)
            if not done.done():
                state.interrupt()
        while not done.done():
            # Cancelling again changes nothing: the thread is still running, so
            # the slot stays taken until it exits.
            with contextlib.suppress(asyncio.CancelledError):
                await asyncio.wait({done})
