"""Sessions a serving engine owns over NATS: whose they are, and their handover.

Transfers, model streams and parked overflow replies live in one process. Their
subjects carry an owner id, so their later messages reach that process only.
In an engine that id is the engine's instance id, the one its lease is held
under (docs/adr/20261006_single-serving-engine.md): hosts built inside
``owned_by(instance_id)`` take it.

At a handover the engine ends its shared (queue-grouped) subscriptions first,
so new requests reach the next engine. A ``SessionHost`` keeps its owner-scoped
subjects until its sessions finish, or until the drain deadline passes
(``nats.engine.drain_seconds``), then closes what is left.

No NATS import: the engine loads this module in every mode.
"""

from __future__ import annotations

import asyncio
import re
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from uuid import uuid4

from naas_abi_core import logger

# How often a host looks whether its sessions have finished.
POLL_SECONDS = 0.05

# Transfer subjects accept 32 lowercase hex characters as an owner
# (``naas_abi_sdk.transfer.transfer_subject``): a uuid4 hex.
_OWNER_ID = re.compile(r"[0-9a-f]{32}")
_engine_owner: ContextVar[str | None] = ContextVar("abi_session_owner", default=None)


def _checked(owner: str) -> str:
    if not _OWNER_ID.fullmatch(owner):
        raise ValueError("A session owner id is 32 lowercase hex characters")
    return owner


@contextmanager
def owned_by(instance_id: str) -> Iterator[None]:
    """Session hosts built inside are owned by the engine ``instance_id``."""
    token = _engine_owner.set(_checked(instance_id))
    try:
        yield
    finally:
        _engine_owner.reset(token)


def session_owner(owner: str | None = None) -> str:
    """``owner`` if given, else the engine's (``owned_by``), else a new id."""
    if owner is not None:
        return _checked(owner)
    return _engine_owner.get() or uuid4().hex


async def until(done: Callable[[], bool]) -> None:
    """Return once ``done()`` is true."""
    while not done():
        await asyncio.sleep(POLL_SECONDS)


class SessionHost(ABC):
    """A NATS endpoint whose sessions outlive its shared subscriptions."""

    @abstractmethod
    async def stop_accepting(self) -> None:
        """End the shared (queue-grouped) subscriptions. Open sessions go on."""

    @abstractmethod
    async def sessions_finished(self) -> None:
        """Return once no session is open."""

    @abstractmethod
    async def stop(self) -> None:
        """End every subscription and close the sessions still open."""


async def wait_for_sessions(
    hosts: Iterable[SessionHost], deadline_seconds: float
) -> bool:
    """Wait for every host's sessions to finish, for up to ``deadline_seconds``.

    True when they all finished, False when the deadline passed first.
    """
    waits = [asyncio.ensure_future(host.sessions_finished()) for host in hosts]
    if not waits:
        return True
    done, pending = await asyncio.wait(waits, timeout=max(0.0, deadline_seconds))
    for task in pending:
        task.cancel()
    await asyncio.gather(*pending, return_exceptions=True)
    for task in done:
        if not task.cancelled() and task.exception() is not None:
            logger.opt(exception=task.exception()).warning(
                "Waiting for a host's sessions failed; closing them"
            )
    return not pending
