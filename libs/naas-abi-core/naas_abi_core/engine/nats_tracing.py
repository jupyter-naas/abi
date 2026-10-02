"""Server spans for kernel services exposed as NATS micro services.

``add_traced_service`` is ``nats.micro.add_service`` whose endpoints run inside a
SERVER span continuing the caller's trace (``traceparent`` header). No-op without
OpenTelemetry. See ``naas_abi_sdk.telemetry``.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import nats.micro
from naas_abi_sdk.telemetry import server_span


def traced_handler(
    handler: Callable[[Any], Awaitable[None]],
) -> Callable[[Any], Awaitable[None]]:
    async def handle(request: Any) -> None:
        with server_span(request.subject, request.headers):
            await handler(request)

    handle.__wrapped__ = handler  # type: ignore[attr-defined]
    return handle


class TracedService:
    """A micro service whose endpoint handlers are traced; everything else delegates."""

    def __init__(self, service: Any) -> None:
        self._service = service

    async def add_endpoint(self, *args: Any, handler: Any, **kwargs: Any) -> Any:
        return await self._service.add_endpoint(
            *args, handler=traced_handler(handler), **kwargs
        )

    def __getattr__(self, name: str) -> Any:
        return getattr(self._service, name)


async def add_traced_service(nc: Any, **config: Any) -> TracedService:
    return TracedService(await nats.micro.add_service(nc, **config))
