"""Stop the process when a NATS connection it depends on closes for good.

nats-py retries a lost server ``max_reconnect_attempts`` times (60, two seconds
apart, by default), then closes the connection and never reconnects it.
Subscriptions, job consumers and the engine's lease all live on such
connections, so the process keeps running but serves nothing, while its HTTP
health check stays green. A process that calls ``exit_on_connection_loss()``
stops instead, and its supervisor (Docker, Kubernetes, ``abi dev``) starts a
fresh one. Otherwise a loss is only logged.

Each connection gets a ``Lifeline``: its ``closed`` is nats-py's ``closed_cb``,
and its owner closes the connection on purpose with ``close(nc)`` (or sets
``closing`` first), which is then not a loss.
"""

from __future__ import annotations

import contextlib
import logging
import os
import signal
import threading
from collections.abc import AsyncIterator, Callable
from typing import Any

logger = logging.getLogger(__name__)

HARD_EXIT_SECONDS = 20.0
"""How long the graceful shutdown may take before the process exits anyway."""

_lock = threading.Lock()
_stop: Callable[[], None] | None = None
_stopping = False


def stop_process() -> None:
    """Shut this process down as an orchestrator would (SIGTERM). If that has
    not ended it within ``HARD_EXIT_SECONDS``, exit with status 1."""
    timer = threading.Timer(HARD_EXIT_SECONDS, os._exit, args=(1,))
    timer.daemon = True
    timer.start()
    os.kill(os.getpid(), signal.SIGTERM)


def exit_on_connection_loss(
    stop: Callable[[], None] | None = stop_process,
) -> Callable[[], None]:
    """Call ``stop`` once when a watched connection is lost (None: only log).

    Returns a function that restores the previous behaviour.
    """
    global _stop, _stopping
    with _lock:
        previous = _stop
        _stop, _stopping = stop, False

    def restore() -> None:
        global _stop, _stopping
        with _lock:
            _stop, _stopping = previous, False

    return restore


@contextlib.asynccontextmanager
async def stopping_on_loss(
    stop: Callable[[], None] | None = stop_process,
) -> AsyncIterator[None]:
    """``exit_on_connection_loss(stop)`` for the duration of the block."""
    restore = exit_on_connection_loss(stop)
    try:
        yield
    finally:
        restore()


def connection_lost(name: str) -> None:
    """Report that the connection ``name`` closed without its owner closing it."""
    global _stopping
    with _lock:
        stop, first = _stop, not _stopping
        if stop is not None:
            _stopping = True
    if stop is None:
        logger.error(
            "NATS connection %s closed for good: this process can no longer reach NATS",
            name,
        )
    elif first:
        logger.critical(
            "NATS connection %s closed for good: stopping the process so that "
            "its supervisor restarts it",
            name,
        )
        stop()


class Lifeline:
    """One connection's ``closed_cb``: a close its owner did not start is a loss."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.closing = False

    async def closed(self) -> None:
        if not self.closing:
            connection_lost(self.name)

    async def close(self, nc: Any) -> None:
        """Close ``nc`` on purpose. One nats-py already closed stays a loss: its
        ``closed_cb`` may run after the owner reacted to the closed connection."""
        if not nc.is_closed:
            self.closing = True
            await nc.close()
