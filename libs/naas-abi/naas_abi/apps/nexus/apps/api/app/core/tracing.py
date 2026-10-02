"""OpenTelemetry SERVER spans for Nexus HTTP requests (pure ASGI middleware).

Continues an incoming ``traceparent`` and names spans after the route template,
so a chat request and every NATS call it makes share one trace. No-op without
OpenTelemetry or a configured tracer provider (``telemetry:`` in the engine config).
"""

from __future__ import annotations

from typing import Any

UNTRACED_PATHS = frozenset({"/health"})


def _tracer() -> Any:
    from opentelemetry import trace

    return trace.get_tracer("naas_abi.nexus")


class TracingMiddleware:
    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope.get("type") != "http" or scope.get("path") in UNTRACED_PATHS:
            await self.app(scope, receive, send)
            return
        try:
            from opentelemetry import propagate
            from opentelemetry.trace import SpanKind, Status, StatusCode
        except ImportError:
            await self.app(scope, receive, send)
            return

        headers = {
            key.decode("latin-1").lower(): value.decode("latin-1")
            for key, value in scope.get("headers") or ()
        }
        method = scope.get("method", "GET")
        with _tracer().start_as_current_span(
            f"{method} {scope.get('path', '')}",
            context=propagate.extract(headers),
            kind=SpanKind.SERVER,
            attributes={"http.request.method": method, "url.path": scope.get("path", "")},
        ) as span:

            async def traced_send(message: dict) -> None:
                if message.get("type") == "http.response.start":
                    status = int(message.get("status", 0))
                    span.set_attribute("http.response.status_code", status)
                    if status >= 500:
                        span.set_status(Status(StatusCode.ERROR, f"HTTP {status}"))
                await send(message)

            try:
                await self.app(scope, receive, traced_send)
            except Exception as exc:
                span.set_status(Status(StatusCode.ERROR, type(exc).__name__))
                raise
            finally:
                route = scope.get("route")
                if route is not None and getattr(route, "path", None):
                    span.update_name(f"{method} {route.path}")
                    span.set_attribute("http.route", route.path)
