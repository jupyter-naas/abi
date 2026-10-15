"""Sessions a serving engine owns over NATS: whose they are, and their handover.

Transfers, model streams and parked overflow replies live in one process. Their
subjects carry an owner id, so their later messages reach that process only.
In an engine that id is the engine's instance id, the one its lease is held
under (docs/adr/20261006_single-serving-engine.md): hosts built inside
``owned_by(instance_id)`` take it.

At a handover the engine ends its shared (queue-grouped) subscriptions first
(``stop_delivery``), so new requests reach the next engine. A ``SessionHost``
keeps its owner-scoped subjects until its sessions finish, or until the drain
deadline passes (``nats.engine.drain_seconds``), then closes what is left. A
kernel primary (``ServicePrimary``) counts the one-shot calls it has received as
sessions.

No NATS import: the engine loads this module in every mode.
"""

from __future__ import annotations

import asyncio
import re
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Iterator
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Any
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


async def stop_delivery(subscriptions: Iterable[Any]) -> None:
    """End nats-py ``subscriptions`` at the broker, keeping what it delivered.

    Returns once the broker has processed the UNSUBs: every message it sent them
    is in their pending queues, which they go on handling. ``Subscription.drain``
    is then safe. On its own it is not: it writes its PING before its UNSUB (a
    PING skips the client's pending buffer), so a message the broker routes in
    between arrives after the drain removed the subscription and is dropped
    (reproduced with concurrent requests on nats-server 2.14).

    Reaches into nats-py: ``Subscription._conn`` and ``_id``,
    ``Client._send_unsubscribe`` and ``_flush_pending``.
    """
    connections: dict[int, Any] = {}
    for subscription in subscriptions:
        nc = subscription._conn
        await nc._send_unsubscribe(subscription._id)
        connections[id(nc)] = nc
    for nc in connections.values():
        await nc._flush_pending(force_flush=True)  # on the socket...
        await nc.flush()  # ...and processed by the broker


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


class ServicePrimary(SessionHost):
    """A kernel primary adapter: one NATS micro service, ``_service`` (a
    ``nats_tracing.TracedService``, None until started), whose handlers run on
    ``_dispatch``, the domain's worker pool.

    The one-shot calls it has received are its sessions: at a handover its
    endpoints stop taking calls, which go to the next engine, and it answers
    those it already has.
    """

    _service: Any
    _dispatch: Any

    async def stop_accepting(self) -> None:
        if self._service is not None:
            await self._service.stop_accepting()

    async def sessions_finished(self) -> None:
        if self._service is not None:
            await self._service.requests_finished()

    async def stop(self) -> None:
        """Deregister the service now: a call still running is cancelled."""
        service, self._service = self._service, None
        try:
            if service is not None:
                await service.stop()
        finally:
            self._dispatch.close()


async def wait_for_sessions(
    hosts: Iterable[SessionHost], deadline_seconds: float
) -> bool:
    """Wait for every host's sessions to finish, for up to ``deadline_seconds``.

    True when they all finished, False when the deadline passed first.

    Waits twice: a call answered during the first wait may have opened a session
    on a host already done, by parking its overflowing reply there. After the
    first wait no call is left to open one.
    """
    hosts = list(hosts)
    if not hosts:
        return True
    loop = asyncio.get_running_loop()
    deadline = loop.time() + max(0.0, deadline_seconds)
    for _ in range(2):
        if not await _wait_once(hosts, deadline - loop.time()):
            return False
    return True


async def _wait_once(hosts: list[SessionHost], seconds: float) -> bool:
    waits = [asyncio.ensure_future(host.sessions_finished()) for host in hosts]
    done, pending = await asyncio.wait(waits, timeout=max(0.0, seconds))
    for task in pending:
        task.cancel()
    await asyncio.gather(*pending, return_exceptions=True)
    for task in done:
        if not task.cancelled() and task.exception() is not None:
            logger.opt(exception=task.exception()).warning(
                "Waiting for a host's sessions failed; closing them"
            )
    return not pending
