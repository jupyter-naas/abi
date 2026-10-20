"""Live NATS traffic for the SysAdmin app: metadata only, never payloads or tokens.

``TrafficEvent`` is one observed call (request paired with its reply) or publish.
``TrafficHub`` runs a single tap while at least one viewer watches and fans events
out through bounded queues: a slow viewer loses old events, it never blocks the tap.
"""

from __future__ import annotations

import asyncio
import base64
import binascii
import contextlib
import json
import re
from collections import deque
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any, Protocol

_TRACEPARENT = re.compile(r"^[0-9a-f]{2}-([0-9a-f]{32})-[0-9a-f]{16}-[0-9a-f]{2}$")


@dataclass(frozen=True)
class TrafficEvent:
    at: float
    kind: str
    subject: str
    service: str
    method: str
    caller: str
    request_bytes: int
    reply_bytes: int | None
    latency_ms: float | None
    status: str  # ok | error | no_reply | published
    error_code: str = ""
    trace_id: str = ""


class TrafficTap(Protocol):
    async def start(self, emit: Callable[[TrafficEvent], None]) -> None:
        """Begin observing; raises SourceUnavailable when NATS cannot be reached."""
        ...

    async def stop(self) -> None: ...


def classify(subject: str) -> tuple[str, str, str]:
    """(kind, service, method) from an ABI subject."""
    parts = subject.split(".")
    if subject.startswith("abi.svc.") and len(parts) >= 5:
        service = parts[2]
        kind = "model" if service == "model_registry" else "service"
        return kind, service, parts[-1]
    if subject.startswith("abi.discovery.") and len(parts) == 5:
        return "discovery", parts[2], parts[4]
    if subject.startswith("abi.agent.") and len(parts) == 7:
        return "agent", f"{parts[2]}/{parts[3]}", parts[6]
    if subject.startswith("abi.jobs.") and len(parts) >= 4:
        return "job", parts[2], parts[3]
    if subject.startswith("evt.") and len(parts) >= 2:
        return "event", parts[1], "publish"
    return "other", "", ""


def caller_from_token(token: str | None) -> str:
    """The ``sub`` claim of a service JWT, read without verifying it (display only)."""
    if not token or token.count(".") != 2:
        return ""
    payload = token.split(".")[1]
    try:
        claims = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
    except (binascii.Error, ValueError, UnicodeDecodeError):
        return ""
    sub = claims.get("sub") if isinstance(claims, dict) else None
    return sub if isinstance(sub, str) else ""


def trace_id_from_traceparent(header: str | None) -> str:
    match = _TRACEPARENT.match(header or "")
    return match.group(1) if match else ""


class Viewer:
    def __init__(self, max_queue: int) -> None:
        self._events: deque[TrafficEvent] = deque()
        self._max = max_queue
        self._ready = asyncio.Event()
        self.dropped = 0

    def push(self, event: TrafficEvent) -> None:
        if len(self._events) >= self._max:
            self._events.popleft()
            self.dropped += 1
        self._events.append(event)
        self._ready.set()

    async def get(self) -> TrafficEvent:
        while not self._events:
            self._ready.clear()
            await self._ready.wait()
        return self._events.popleft()

    def drain(self, limit: int) -> list[TrafficEvent]:
        """What is already queued, up to ``limit``, without waiting."""
        batch: list[TrafficEvent] = []
        while self._events and len(batch) < limit:
            batch.append(self._events.popleft())
        return batch


class TrafficHub:
    def __init__(self, tap_factory: Callable[[], TrafficTap], *, max_queue: int = 2000) -> None:
        self._tap_factory = tap_factory
        self._max_queue = max_queue
        self._viewers: set[Viewer] = set()
        self._tap: TrafficTap | None = None
        self._lock = asyncio.Lock()

    @property
    def source(self) -> str | None:
        """Where the running tap reads traffic from (``traces`` or ``nats``)."""
        return getattr(self._tap, "source", None) if self._tap is not None else None

    @property
    def skipped(self) -> dict[str, str]:
        """Sources passed over to reach ``source``, with why."""
        return dict(getattr(self._tap, "skipped", {}) or {}) if self._tap is not None else {}

    def _emit(self, event: TrafficEvent) -> None:
        for viewer in list(self._viewers):
            viewer.push(event)

    @contextlib.asynccontextmanager
    async def subscribe(self) -> AsyncIterator[Viewer]:
        viewer = Viewer(self._max_queue)
        async with self._lock:
            # Registered before the tap starts: nothing it emits early is lost.
            self._viewers.add(viewer)
            if self._tap is None:
                tap = self._tap_factory()
                try:
                    await tap.start(self._emit)
                except BaseException:
                    self._viewers.discard(viewer)
                    raise
                self._tap = tap
        try:
            yield viewer
        finally:
            async with self._lock:
                self._viewers.discard(viewer)
                if not self._viewers and self._tap is not None:
                    tap, self._tap = self._tap, None
                    with contextlib.suppress(Exception):
                        await tap.stop()


def event_json(event: TrafficEvent) -> dict[str, Any]:
    return {field: getattr(event, field) for field in event.__dataclass_fields__}
