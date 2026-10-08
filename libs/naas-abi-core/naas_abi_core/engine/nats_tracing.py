"""Kernel services exposed as NATS micro services: server spans, concurrency, handover.

``add_traced_service`` is ``nats.micro.add_service`` whose endpoints run inside a
SERVER span continuing the caller's trace (``traceparent`` header). No-op without
OpenTelemetry. See ``naas_abi_sdk.telemetry``.

Calls run side by side, up to ``max_concurrency`` at once for the whole service
(``ConcurrentRequests``, ``nats.max_concurrent_requests``).

At a handover the service stops taking calls but answers those it already
received (``stop_accepting``, ``requests_finished``); see
docs/adr/20261006_single-serving-engine.md.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextlib import suppress
from typing import Any

import nats.errors
import nats.micro
from naas_abi_core.engine.nats_dispatch import max_concurrent_requests
from naas_abi_core.engine.nats_sessions import stop_delivery, until
from naas_abi_sdk.concurrency import ConcurrentCalls
from naas_abi_sdk.telemetry import server_span


def traced_handler(
    handler: Callable[[Any], Awaitable[None]],
) -> Callable[[Any], Awaitable[None]]:
    async def handle(request: Any) -> None:
        with server_span(request.subject, request.headers):
            await handler(request)

    handle.__wrapped__ = handler  # type: ignore[attr-defined]
    return handle


class ConcurrentRequests(ConcurrentCalls):
    """A kernel service's calls side by side (``naas_abi_sdk.concurrency``).

    The callback is ``nats.micro``'s own request handler, which keeps the
    endpoint statistics (``$SRV.STATS``) and answers a handler's exception with
    a 500 error reply.
    """

    def client(self, nc: Any) -> Any:
        """``nc`` for ``nats.micro``: endpoint subscriptions run their calls here."""
        return _ConcurrentClient(nc, self)


class _ConcurrentClient:
    """A NATS client whose queue subscriptions, ``nats.micro``'s endpoints, run
    their calls through ``ConcurrentRequests``. Its own verb subscriptions
    (``$SRV.PING``, ``INFO``, ``STATS``) have no queue group and stay as they are."""

    def __init__(self, nc: Any, requests: ConcurrentRequests) -> None:
        self._nc = nc
        self._requests = requests

    async def subscribe(self, *args: Any, **kwargs: Any) -> Any:
        if kwargs.get("queue") and kwargs.get("cb") is not None:
            kwargs["cb"] = self._requests.callback(kwargs["cb"])
        return await self._nc.subscribe(*args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._nc, name)


class TracedService:
    """A micro service whose endpoint handlers are traced; everything else delegates."""

    def __init__(
        self, service: Any, requests: ConcurrentRequests | None = None
    ) -> None:
        self._service = service
        self._requests = requests or ConcurrentRequests(max_concurrent_requests())
        self._draining: list[Any] = []  # endpoint subscriptions the broker has ended

    async def add_endpoint(self, *args: Any, handler: Any, **kwargs: Any) -> Any:
        return await self._service.add_endpoint(
            *args, handler=traced_handler(handler), **kwargs
        )

    async def stop_accepting(self) -> None:
        """End the endpoints' queue-group subscriptions at the broker, so new calls
        go to the group's other members. Calls already received run and are answered.

        ``nats.micro``'s own stop unsubscribes, which cancels a handler still
        running and drops the calls already delivered: their callers time out.
        This reaches into ``nats.micro`` (``Service._endpoints``,
        ``Endpoint._subscription``) to end each endpoint's subscription gracefully.
        """
        endpoints, self._service._endpoints = self._service._endpoints, []
        subscriptions = [e._subscription for e in endpoints if e._subscription]
        self._draining += subscriptions
        await stop_delivery(subscriptions)

    async def requests_finished(self) -> None:
        """Return once every call received before ``stop_accepting`` is answered."""
        await until(
            lambda: (
                not self._requests.in_flight
                and not any(sub.pending_msgs for sub in self._draining)
            )
        )

    async def stop(self) -> None:
        """Stop now. A call still running (fencing, or past the drain deadline) is
        cancelled, and the calls waiting behind it are dropped."""
        draining, self._draining = self._draining, []
        for subscription in draining:
            with suppress(nats.errors.Error):  # already gone with the connection
                await subscription.unsubscribe()
        await self._service.stop()
        await self._requests.cancel()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._service, name)


async def add_traced_service(
    nc: Any, *, max_concurrency: int | None = None, **config: Any
) -> TracedService:
    """``nats.micro.add_service`` with traced endpoints whose calls run side by
    side, up to ``max_concurrency`` at once (default: ``nats.max_concurrent_requests``)."""
    requests = ConcurrentRequests(
        max_concurrent_requests() if max_concurrency is None else max_concurrency
    )
    service = await nats.micro.add_service(requests.client(nc), **config)
    return TracedService(service, requests)
