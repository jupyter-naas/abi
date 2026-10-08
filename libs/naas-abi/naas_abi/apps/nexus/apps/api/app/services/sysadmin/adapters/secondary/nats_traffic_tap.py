"""Observe ABI traffic on the broker: requests paired with replies, and publishes.

Subscribes to ABI request subjects only (kernel services, discovery, agents, jobs,
events) and to ``_INBOX.>`` to pair replies. Chunked transfer subjects are left out
on purpose. Only headers and sizes are read: never payloads, never the token
(the caller is its ``sub`` claim). Replies to requests that were not observed are
dropped on arrival, but still cross the wire: run the tap only while watched.
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from collections import OrderedDict
from collections.abc import Awaitable, Callable
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import SourceUnavailable
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.traffic import (
    TrafficEvent,
    caller_from_token,
    classify,
    trace_id_from_traceparent,
)

TAP_SUBJECTS = (
    "abi.svc.*.v1.*",  # kernel services and the model registry (5 tokens: not transfers)
    "abi.svc.cache.v1.tier.*.*",
    "abi.discovery.*.v1.*",
    "abi.agent.>",
    "abi.jobs.>",
    "evt.>",
)
REPLIES = "_INBOX.>"
AUTH_HEADER = "Nats-Auth-Token"
ERROR_HEADERS = ("Abi-Error-Code", "Nats-Service-Error-Code")


class NatsTrafficTap:
    source = "nats"

    def __init__(
        self,
        connect: Callable[[], Awaitable[Any]],
        *,
        reply_timeout_seconds: float = 60.0,
        max_pending: int = 10_000,
        sweep_seconds: float = 1.0,
        connect_timeout_seconds: float = 3.0,
        clock: Callable[[], float] = time.time,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        self._connect = connect
        self._reply_timeout = reply_timeout_seconds
        self._max_pending = max_pending
        self._sweep_every = sweep_seconds
        self._connect_timeout = connect_timeout_seconds
        self._clock, self._monotonic = clock, monotonic
        self._pending: OrderedDict[str, tuple[dict[str, Any], float]] = OrderedDict()
        self._subscriptions: list[Any] = []
        self._sweeper: asyncio.Task | None = None
        self._emit: Callable[[TrafficEvent], None] = lambda event: None

    async def start(self, emit: Callable[[TrafficEvent], None]) -> None:
        self._emit = emit
        try:
            nc = await asyncio.wait_for(self._connect(), self._connect_timeout)
            for subject in TAP_SUBJECTS:
                self._subscriptions.append(await nc.subscribe(subject, cb=self._on_request))
            self._subscriptions.append(await nc.subscribe(REPLIES, cb=self._on_reply))
        except Exception as exc:  # noqa: BLE001 - no broker, refused, timed out
            await self.stop()
            reason = "timed out connecting" if isinstance(exc, asyncio.TimeoutError) else str(exc)
            raise SourceUnavailable("nats", reason or type(exc).__name__) from exc
        self._sweeper = asyncio.create_task(self._sweep())

    async def stop(self) -> None:
        if self._sweeper is not None:
            self._sweeper.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._sweeper
            self._sweeper = None
        subscriptions, self._subscriptions = self._subscriptions, []
        for subscription in subscriptions:
            with contextlib.suppress(Exception):
                await subscription.unsubscribe()
        self._pending.clear()

    async def _on_request(self, msg: Any) -> None:
        kind, service, method = classify(msg.subject)
        headers = msg.headers or {}
        base = {
            "at": self._clock(),
            "kind": kind,
            "subject": msg.subject,
            "service": service,
            "method": method,
            "caller": caller_from_token(headers.get(AUTH_HEADER)),
            "request_bytes": len(msg.data or b""),
            "trace_id": trace_id_from_traceparent(headers.get("traceparent")),
        }
        if not msg.reply:
            self._emit(TrafficEvent(**base, reply_bytes=None, latency_ms=None, status="published"))
            return
        self._pending[msg.reply] = (base, self._monotonic())
        while len(self._pending) > self._max_pending:
            _, (oldest, _) = self._pending.popitem(last=False)
            self._unanswered(oldest)

    async def _on_reply(self, msg: Any) -> None:
        entry = self._pending.pop(msg.subject, None)
        if entry is None:
            return
        base, started = entry
        headers = msg.headers or {}
        code = next((headers[h] for h in ERROR_HEADERS if headers.get(h)), "")
        self._emit(
            TrafficEvent(
                **base,
                reply_bytes=len(msg.data or b""),
                latency_ms=round((self._monotonic() - started) * 1000, 3),
                status="error" if code else "ok",
                error_code=str(code),
            )
        )

    def _unanswered(self, base: dict[str, Any]) -> None:
        self._emit(TrafficEvent(**base, reply_bytes=None, latency_ms=None, status="no_reply"))

    async def _sweep(self) -> None:
        while True:
            await asyncio.sleep(self._sweep_every)
            deadline = self._monotonic() - self._reply_timeout
            while self._pending:
                reply, (base, started) = next(iter(self._pending.items()))
                if started > deadline:
                    break
                del self._pending[reply]
                self._unanswered(base)
