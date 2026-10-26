"""Stopping a tool call that a caller gave up on (``abi.tool.v1`` and
``abi.tool_registry.v1``: ``call_id`` and ``CancelToolRequest``).

A caller names a call with a ``call_id``; the process running it keeps the call in
``ActiveCalls`` under the verified identity of its caller, so only that identity can
cancel it. Cancelling does two things: it sets the call's ``ToolCancellation`` (a
synchronous handler polls it: Python cannot interrupt a thread) and it runs what the
runner registered (an async handler's task is cancelled at its next await).

``ActiveCalls`` is for one event loop: every method is called from it.
"""

from __future__ import annotations

import logging
import re
import threading
import time
import uuid
from collections import OrderedDict
from collections.abc import Callable
from contextvars import ContextVar, Token

logger = logging.getLogger(__name__)

MAX_CALL_ID_CHARS = 128
_CALL_ID = re.compile(r"[A-Za-z0-9_-]{1,128}")
# A cancel that comes before its call is registered (the call is still being
# authorized) is kept this long, for this many calls at most.
EARLY_CANCEL_SECONDS = 30.0
MAX_EARLY_CANCELS = 1024


def new_call_id() -> str:
    return uuid.uuid4().hex


def valid_call_id(value: str) -> bool:
    return _CALL_ID.fullmatch(value) is not None


class ToolCancelled(Exception):
    """Raised by ``ToolCancellation.raise_if_cancelled``: the call was cancelled."""


class ToolCancellation:
    """Whether a call was cancelled. Safe to read from any thread."""

    def __init__(self) -> None:
        self._event = threading.Event()

    @property
    def cancelled(self) -> bool:
        return self._event.is_set()

    def cancel(self) -> None:
        self._event.set()

    def wait(self, timeout: float | None = None) -> bool:
        """Block until cancelled or ``timeout``: ``True`` when cancelled. Use it in
        place of ``time.sleep`` in a synchronous handler."""
        return self._event.wait(timeout)

    def raise_if_cancelled(self) -> None:
        if self._event.is_set():
            raise ToolCancelled("The call was cancelled")


_current: ContextVar[ToolCancellation | None] = ContextVar(
    "naas_abi_tool_cancellation", default=None
)


def current_cancellation() -> ToolCancellation:
    """The cancellation of the tool call running in this context; one that is never
    set outside a call, so a tool can poll it without checking."""
    return _current.get() or ToolCancellation()


def bind_cancellation(token: ToolCancellation) -> Token[ToolCancellation | None]:
    return _current.set(token)


def reset_cancellation(token: Token[ToolCancellation | None]) -> None:
    _current.reset(token)


class CallIdInUse(ValueError):
    """The caller already has a running call with this id."""


class Registration:
    """One running call. ``on_cancel`` runs a callback when it is cancelled (at once
    if it already was)."""

    def __init__(self, release: Callable[[], None]) -> None:
        self._release = release
        self._callbacks: list[Callable[[], None]] = []
        self.cancelled = False

    def on_cancel(self, callback: Callable[[], None]) -> None:
        if self.cancelled:
            self._run(callback)
        else:
            self._callbacks.append(callback)

    def trigger(self) -> None:
        if self.cancelled:
            return
        self.cancelled = True
        callbacks, self._callbacks = self._callbacks, []
        for callback in callbacks:
            self._run(callback)

    @staticmethod
    def _run(callback: Callable[[], None]) -> None:
        try:
            callback()
        except Exception:  # one callback never stops the others
            logger.exception("A tool cancellation callback failed")

    def release(self) -> None:
        self._release()


class ActiveCalls:
    def __init__(
        self,
        *,
        clock: Callable[[], float] = time.monotonic,
        early_seconds: float = EARLY_CANCEL_SECONDS,
        max_early: int = MAX_EARLY_CANCELS,
    ) -> None:
        self._clock = clock
        self._early_seconds = early_seconds
        self._max_early = max_early
        self._active: dict[tuple[str, str], Registration] = {}
        self._early: OrderedDict[tuple[str, str], float] = OrderedDict()

    @property
    def early_count(self) -> int:
        return len(self._early)

    def register(self, identity: str, call_id: str) -> Registration:
        key = (identity, call_id)
        if key in self._active:
            raise CallIdInUse(call_id)
        registration = Registration(lambda: self._forget(key, registration))
        self._active[key] = registration
        self._expire()
        if self._early.pop(key, None) is not None:
            registration.trigger()
        return registration

    def cancel(self, identity: str, call_id: str) -> bool:
        """Cancel ``identity``'s running call ``call_id``; ``False`` when it has none
        (the cancel is then kept briefly, for a call about to register)."""
        key = (identity, call_id)
        registration = self._active.get(key)
        if registration is not None:
            registration.trigger()
            return True
        self._early[key] = self._clock()
        self._early.move_to_end(key)
        while len(self._early) > self._max_early:
            self._early.popitem(last=False)
        return False

    def _forget(self, key: tuple[str, str], registration: Registration) -> None:
        if self._active.get(key) is registration:
            del self._active[key]

    def _expire(self) -> None:
        horizon = self._clock() - self._early_seconds
        while self._early and next(iter(self._early.values())) < horizon:
            self._early.popitem(last=False)
