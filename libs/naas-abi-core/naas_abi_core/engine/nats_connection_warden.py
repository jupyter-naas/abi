"""Module connections end when IAM changes (ADR 20261119_kick_connections_on_iam_change).

The broker fixes a connection's permissions when the auth callout admits it.
The callout records each admission here (``Admissions``); the warden, logged in
to the broker's system account, ends the connections a change affects:

- after an IAM change (one made in this process, or the store's revision
  moving), each recorded connection is checked
  (``IAMService.connection_permissions``): a key no longer usable, an account
  no longer active, or permissions that differ from those it was admitted with
  end the connection (``$SYS.REQ.SERVER.<id>.KICK``). nats-py reconnects it,
  and the callout grants the new subjects or refuses;
- at start and every ``sweep_seconds``, the broker's connections are listed
  (``CONNZ``): one the callout admitted before this engine (it carries an
  ``issuer_key``, the static users do not) is ended so that it logs in again
  here; a recorded one that is gone is forgotten.

Kicks are paced (``kicks_per_second``): an engine restart ends every module
connection once, never all at the same instant.
"""

from __future__ import annotations

import asyncio
import json
import threading
import time
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

import nats
from naas_abi_core import logger
from naas_abi_core.engine.nats_naming import connection_name
from naas_abi_core.services.iam.broker import BrokerPermissions
from naas_abi_core.services.iam.IAMPorts import KeyRefusedError

CONNZ_ALL = "$SYS.REQ.SERVER.PING.CONNZ"
CONNZ_SERVER = "$SYS.REQ.SERVER.{server}.CONNZ"
KICK = "$SYS.REQ.SERVER.{server}.KICK"
# Connections asked of one server per CONNZ page.
CONNZ_PAGE = 1024
# How long a PING.CONNZ waits for the answers of every server of a cluster.
GATHER_SECONDS = 0.5


@dataclass(frozen=True)
class Connection:
    """A client connection, as the broker names it."""

    server_id: str
    client_id: int


@dataclass(frozen=True)
class Admitted:
    """What the callout admitted a connection as."""

    principal_id: str
    key_id: str
    permissions: BrokerPermissions


class Admissions:
    """The connections the callout admitted, written from its worker threads."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._admitted: dict[Connection, Admitted] = {}

    def admit(self, connection: Connection, admitted: Admitted) -> None:
        with self._lock:
            self._admitted[connection] = admitted

    def forget(self, connection: Connection) -> None:
        with self._lock:
            self._admitted.pop(connection, None)

    def get(self, connection: Connection) -> Admitted | None:
        with self._lock:
            return self._admitted.get(connection)

    def snapshot(self) -> dict[Connection, Admitted]:
        with self._lock:
            return dict(self._admitted)

    def __len__(self) -> int:
        with self._lock:
            return len(self._admitted)


def stale(
    admitted: dict[Connection, Admitted],
    permissions: Callable[[str, str], BrokerPermissions],
) -> list[Connection]:
    """The connections whose key, account or permissions changed since they
    were admitted. ``permissions(principal_id, key_id)`` raises
    ``KeyRefusedError`` for a key or account that no longer admits; any other
    error ends the connection too: nothing undecided keeps its subjects. Each
    (account, key) is computed once."""
    decided: dict[tuple[str, str], BrokerPermissions | None] = {}
    ended: list[Connection] = []
    for connection, admission in admitted.items():
        pair = (admission.principal_id, admission.key_id)
        if pair not in decided:
            try:
                decided[pair] = permissions(*pair)
            except KeyRefusedError:
                decided[pair] = None
            except Exception as exc:  # noqa: BLE001 - fail closed
                logger.warning(
                    "Connection warden: could not check a connection of "
                    f"{admission.principal_id}; ending it ({type(exc).__name__})"
                )
                decided[pair] = None
        if decided[pair] != admission.permissions:
            ended.append(connection)
    return ended


def unknown(
    servers: Iterable[dict[str, Any]], admitted: dict[Connection, Admitted]
) -> tuple[list[Connection], list[Connection]]:
    """From CONNZ answers: the callout connections this engine did not admit,
    and the recorded connections the broker no longer has."""
    listed: set[Connection] = set()
    foreign: list[Connection] = []
    answered: set[str] = set()
    for answer in servers:
        server = str((answer.get("server") or {}).get("id", ""))
        answered.add(server)
        for client in (answer.get("data") or {}).get("connections") or ():
            if not client.get("issuer_key"):
                continue  # a static user (engine, auth, sys): never the callout's
            connection = Connection(server, int(client["cid"]))
            listed.add(connection)
            if connection not in admitted:
                foreign.append(connection)
    gone = [c for c in admitted if c.server_id in answered and c not in listed]
    return foreign, gone


class ConnectionWarden:
    def __init__(
        self,
        iam: Any,
        admissions: Admissions,
        system_url: str,
        *,
        sweep_seconds: float = 300.0,
        first_sweep_seconds: float = 10.0,
        revision_check_seconds: float = 2.0,
        settle_seconds: float = 0.5,
        kicks_per_second: float = 20.0,
    ) -> None:
        self.iam = iam
        self.admissions = admissions
        self.system_url = system_url
        self.sweep_seconds = sweep_seconds
        self.first_sweep_seconds = first_sweep_seconds
        self.revision_check_seconds = revision_check_seconds
        self.settle_seconds = settle_seconds
        self.kick_interval = 1.0 / kicks_per_second if kicks_per_second > 0 else 0.0
        self._nc: Any = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._changed: asyncio.Event | None = None
        self._tasks: list[asyncio.Task] = []
        self._revision: int | None = None
        self._kick_lock: asyncio.Lock | None = None

    async def start(self) -> None:
        self._loop = asyncio.get_running_loop()
        self._changed = asyncio.Event()
        self._kick_lock = asyncio.Lock()
        self._nc = await nats.connect(
            self.system_url, name=connection_name("abi-engine:connection-warden")
        )
        self._revision = await asyncio.to_thread(self.iam.store.revision)
        self.iam.add_change_listener(self._on_change)
        self._tasks = [
            asyncio.create_task(self._watch_changes()),
            asyncio.create_task(self._watch_revision()),
            asyncio.create_task(self._sweep_periodically()),
        ]
        logger.info("NATS connection warden: module connections end on IAM changes")

    async def stop(self) -> None:
        self.iam.remove_change_listener(self._on_change)
        for task in self._tasks:
            task.cancel()
        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []
        nc, self._nc = self._nc, None
        if nc is not None:
            await nc.close()

    # -- triggers -------------------------------------------------------------

    def _on_change(self, _revision: int) -> None:
        """IAM's listener: called on the thread that wrote."""
        loop, changed = self._loop, self._changed
        if loop is not None and changed is not None and not loop.is_closed():
            loop.call_soon_threadsafe(changed.set)

    async def _watch_revision(self) -> None:
        """Another process's writes: the store's revision moves."""
        while True:
            await asyncio.sleep(self.revision_check_seconds)
            try:
                revision = await asyncio.to_thread(self.iam.store.revision)
            except Exception as exc:  # noqa: BLE001 - check everything then
                logger.warning(f"Connection warden: IAM revision unreadable ({exc!r})")
                revision = None
            if revision is None or revision != self._revision:
                self._revision = revision
                assert self._changed is not None
                self._changed.set()

    async def _watch_changes(self) -> None:
        assert self._changed is not None
        while True:
            await self._changed.wait()
            # Several writes of one operation: checked once, after them.
            await asyncio.sleep(self.settle_seconds)
            self._changed.clear()
            try:
                await self.check()
            except Exception:  # noqa: BLE001 - the next change or sweep retries
                logger.exception("Connection warden: check after an IAM change failed")

    async def _sweep_periodically(self) -> None:
        delay = self.first_sweep_seconds
        while True:
            await asyncio.sleep(delay)
            delay = self.sweep_seconds
            try:
                await self.sweep()
            except Exception:  # noqa: BLE001 - the next sweep retries
                logger.exception("Connection warden: sweep failed")

    # -- work -----------------------------------------------------------------

    async def check(self) -> list[Connection]:
        """End the recorded connections a change affects; return them."""
        admitted = self.admissions.snapshot()
        if not admitted:
            return []
        ended = await asyncio.to_thread(
            stale, admitted, self.iam.connection_permissions
        )
        if ended:
            logger.info(
                f"Connection warden: {len(ended)} of {len(admitted)} module "
                "connection(s) changed; ending them"
            )
            await self.kick(ended)
        return ended

    async def sweep(self) -> list[Connection]:
        """End the callout connections this engine did not admit, forget the
        recorded ones that are gone, then check the rest. Return those ended."""
        answers = await self._connz()
        foreign, gone = unknown(answers, self.admissions.snapshot())
        for connection in gone:
            self.admissions.forget(connection)
        if foreign:
            logger.info(
                f"Connection warden: {len(foreign)} module connection(s) admitted "
                "before this engine; ending them so that they log in here"
            )
            await self.kick(foreign)
        return foreign + await self.check()

    async def kick(self, connections: Iterable[Connection]) -> None:
        assert self._kick_lock is not None
        async with self._kick_lock:
            for connection in connections:
                self.admissions.forget(connection)
                try:
                    await self._nc.request(
                        KICK.format(server=connection.server_id),
                        json.dumps({"cid": connection.client_id}).encode(),
                        timeout=2,
                    )
                except Exception as exc:  # noqa: BLE001 - gone already, or the next sweep
                    logger.warning(
                        f"Connection warden: could not end connection "
                        f"{connection.client_id} ({type(exc).__name__})"
                    )
                if self.kick_interval:
                    await asyncio.sleep(self.kick_interval)

    async def _connz(self) -> list[dict[str, Any]]:
        """Every server's client connections, with their auth details."""
        inbox = self._nc.new_inbox()
        answers: list[dict[str, Any]] = []
        subscription = await self._nc.subscribe(inbox)
        try:
            query = {"auth": True, "limit": CONNZ_PAGE}
            await self._nc.publish(CONNZ_ALL, json.dumps(query).encode(), reply=inbox)
            deadline = time.monotonic() + GATHER_SECONDS
            while (left := deadline - time.monotonic()) > 0:
                try:
                    msg = await subscription.next_msg(timeout=left)
                except (TimeoutError, nats.errors.TimeoutError):
                    break
                answers.append(json.loads(msg.data))
        finally:
            await subscription.unsubscribe()
        for answer in answers:
            await self._remaining_pages(answer)
        return answers

    async def _remaining_pages(self, answer: dict[str, Any]) -> None:
        data = answer.get("data") or {}
        connections = data.setdefault("connections", [])
        total = int(data.get("total") or 0)
        server = str((answer.get("server") or {}).get("id", ""))
        while server and len(connections) < total:
            query = {"auth": True, "limit": CONNZ_PAGE, "offset": len(connections)}
            msg = await self._nc.request(
                CONNZ_SERVER.format(server=server),
                json.dumps(query).encode(),
                timeout=2,
            )
            page = (json.loads(msg.data).get("data") or {}).get("connections") or []
            if not page:
                break
            connections.extend(page)
