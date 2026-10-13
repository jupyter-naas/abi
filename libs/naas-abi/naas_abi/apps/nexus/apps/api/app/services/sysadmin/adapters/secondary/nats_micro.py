"""Kernel service stats from the NATS micro protocol (``$SRV.STATS``).

Every micro service instance answers ``$SRV.STATS``, so the request is published
once with a private inbox and replies are collected until none arrives for
``idle_seconds`` (or ``wait_seconds`` overall). Discovery, the model registry and
agents are plain subscriptions and do not answer here.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Awaitable, Callable
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import (
    EndpointStats,
    MicroServiceInstance,
    SourceUnavailable,
)

STATS_SUBJECT = "$SRV.STATS"
STATS_TYPE = "io.nats.micro.v1.stats_response"
MAX_REPLIES = 1024


def _ms(nanoseconds: Any) -> float:
    try:
        return round(float(nanoseconds) / 1_000_000, 3)
    except (TypeError, ValueError):
        return 0.0


def parse_stats(body: Any) -> MicroServiceInstance | None:
    if not isinstance(body, dict) or body.get("type") != STATS_TYPE:
        return None
    endpoints = tuple(
        EndpointStats(
            name=str(e.get("name", "")),
            subject=str(e.get("subject", "")),
            requests=int(e.get("num_requests", 0) or 0),
            errors=int(e.get("num_errors", 0) or 0),
            average_ms=_ms(e.get("average_processing_time", 0)),
            last_error=str(e.get("last_error", "") or ""),
        )
        for e in body.get("endpoints") or ()
        if isinstance(e, dict)
    )
    return MicroServiceInstance(
        name=str(body.get("name", "")),
        instance_id=str(body.get("id", "")),
        version=str(body.get("version", "")),
        started=str(body.get("started", "")),
        endpoints=endpoints,
    )


class NatsMicroServiceMonitor:
    def __init__(
        self,
        connect: Callable[[], Awaitable[Any]],
        *,
        wait_seconds: float = 1.0,
        idle_seconds: float = 0.25,
        connect_timeout_seconds: float = 3.0,
    ) -> None:
        self._connect = connect
        self._connect_timeout = connect_timeout_seconds
        self._wait = wait_seconds
        self._idle = idle_seconds

    async def list_instances(self) -> list[MicroServiceInstance]:
        from nats.errors import TimeoutError as NATSTimeoutError

        try:
            # A dashboard must not wait for nats-py's reconnect loop.
            nc = await asyncio.wait_for(self._connect(), self._connect_timeout)
            inbox = nc.new_inbox()
            sub = await nc.subscribe(inbox)
        except Exception as exc:  # noqa: BLE001 - any connection failure means "unavailable"
            reason = "timed out connecting" if isinstance(exc, asyncio.TimeoutError) else str(exc)
            raise SourceUnavailable("nats", reason or type(exc).__name__) from exc
        instances: list[MicroServiceInstance] = []
        try:
            await nc.publish(STATS_SUBJECT, b"", reply=inbox)
            loop = asyncio.get_running_loop()
            deadline = loop.time() + self._wait
            while len(instances) < MAX_REPLIES:
                remaining = deadline - loop.time()
                if remaining <= 0:
                    break
                try:
                    msg = await sub.next_msg(timeout=min(self._idle, remaining))
                except (TimeoutError, NATSTimeoutError):
                    break
                try:
                    parsed = parse_stats(json.loads(msg.data))
                except (ValueError, TypeError):
                    continue
                if parsed is not None:
                    instances.append(parsed)
        finally:
            try:
                await sub.unsubscribe()
            except Exception:  # noqa: BLE001 - the connection may be closing
                pass
        return sorted(instances, key=lambda i: (i.name, i.instance_id))
