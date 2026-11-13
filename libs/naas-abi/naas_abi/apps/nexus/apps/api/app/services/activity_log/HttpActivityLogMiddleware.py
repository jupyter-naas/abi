"""Pure-ASGI HTTP activity-log middleware (Sentry-style).

Wraps the downstream ASGI app to:
- accumulate request body chunks as they stream in (capped),
- observe the response status,
- record one ``http.request`` ActivityEvent per request,
without disrupting the downstream handler.

A request body is recorded only for a route that opts in: its JSON body model names
the fields the log keeps (``activity_log_fields``, a class attribute). Those fields
are kept, any key that names a credential redacted within them; every other body is
recorded as its size. Plain-text and form bodies are never recorded, nor any body of
the routes that carry credentials (``DEFAULT_SKIP_BODY_PATH_PREFIXES``). Query
parameters are kept, redacted the same way. ``redact_recorded`` applies the same rules
to an event recorded before them, as it is read back.

Lives in Nexus rather than naas-abi-core because it knows what an HTTP
request is (ASGI); core knows nothing about it.

The actor is never read from the request: it is the request's verified
caller, set by ``RequestIdentityMiddleware`` around this one (``api`` on
behalf of the signed-in user), and the activity log records under the call's
user. A request with no signed-in user is recorded as Nexus's own ``api``
account, with ``anonymous: true``, so failed sign-ins stay on the record.

During a view (``services/view_as``) the call is the person's, but the request is the
viewer's act: the event is recorded under the viewer, with the person and the workspace
viewed as the attribute ``view_as``. Nothing is recorded as the person's activity.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections.abc import Iterable
from dataclasses import replace
from typing import Any
from urllib.parse import parse_qsl

from naas_abi.apps.nexus.apps.api.app.services.apps.remote.grant import redact_grant_path
from naas_abi.apps.nexus.apps.api.app.services.view_as.active import current_view
from naas_abi_core.engine.call_context import (
    Principal,
    as_service_account,
    current_call_context,
    use_call_context,
)
from naas_abi_core.services.activity_log.ActivityLogPort import ActivityEvent
from naas_abi_core.services.activity_log.ActivityLogService import (
    ActivityLogService,
    call_actor,
)
from starlette.datastructures import Headers
from starlette.types import ASGIApp, Message, Receive, Scope, Send

# A JSON key or query parameter whose name contains one of these (case-insensitive)
# may hold a credential: its value is never recorded.
SENSITIVE_KEY_PARTS: tuple[str, ...] = (
    "password",
    "passwd",
    "secret",
    "key",
    "token",
    "auth",
    "credential",
    "session",
    "csrf",
    "cookie",
    "code",
    "otp",
    "env",
    "signature",
)

REDACTED = "[REDACTED]"
# The class attribute of a route's body model naming the fields the log keeps.
RECORDED_FIELDS = "activity_log_fields"

DEFAULT_MAX_BODY_BYTES = 64 * 1024  # 64 KB
# Routes whose bodies carry credentials or raw service values: never recorded, even
# by a route that opts in.
DEFAULT_SKIP_BODY_PATH_PREFIXES: tuple[str, ...] = (
    "/api/auth/",
    "/api/admin/system/resources/",
    "/api/secrets",
    "/api/iam/token",
    "/idp/",
)
# Liveness probes (container healthcheck, proxy) hit these every few seconds;
# recording them would fill the anonymous log with noise.
DEFAULT_SKIP_RECORD_PATHS: frozenset[str] = frozenset({"/", "/health"})


def is_sensitive(name: str) -> bool:
    lowered = str(name).lower()
    return any(part in lowered for part in SENSITIVE_KEY_PARTS)


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: (REDACTED if is_sensitive(k) else _redact(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(v) for v in value]
    return value


def _redact_pairs(pairs: Iterable[tuple[str, str]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in pairs:
        out[k] = REDACTED if is_sensitive(k) else v
    return out


def _is_json(content_type: str) -> bool:
    ct = content_type.split(";", 1)[0].strip().lower()
    return ct == "application/json" or ct.endswith("+json")


def recorded_fields(route: Any) -> frozenset[str] | None:
    """The body fields ``route`` lets the log keep: its JSON body model's
    ``activity_log_fields``. None when it keeps none (no such model, or no list)."""
    dependant = getattr(route, "dependant", None)
    params = list(getattr(dependant, "body_params", None) or [])
    if len(params) != 1:
        return None
    model = getattr(params[0], "type_", None)
    fields = getattr(model, RECORDED_FIELDS, None) if isinstance(model, type) else None
    if not fields:
        return None
    return frozenset(str(f) for f in fields)


def _kept_body(raw: bytes, fields: frozenset[str]) -> dict[str, Any] | None:
    """The fields of a JSON object body that the route keeps, redacted within."""
    try:
        decoded = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(decoded, dict):
        return None
    return {k: _redact(v) for k, v in decoded.items() if k in fields and not is_sensitive(k)}


def skipped_body(reason: str, size: int | None) -> str:
    return f"[{reason.upper()}" + (f":{size}" if size is not None else "") + "]"


def _is_skip_marker(value: Any) -> bool:
    return isinstance(value, str) and value.startswith("[") and value.endswith("]")


def redact_recorded(
    attributes: dict[str, Any] | None,
    skip_body_path_prefixes: tuple[str, ...] = (),
) -> dict[str, Any]:
    """An ``http.request`` event's attributes as these rules would have recorded
    them: for one recorded before them, read back. A body shows only when the event
    says which fields its route kept (``request_body_kept``), and only those fields,
    every key that names a credential redacted; any other body (an older event's, a
    credential route's, text or a form) shows as its size. Query parameters are
    redacted the same way."""
    attrs = dict(attributes or {})
    prefixes = skip_body_path_prefixes or DEFAULT_SKIP_BODY_PATH_PREFIXES
    path = str(attrs.get("path") or "")
    body = attrs.get("request_body")
    if "request_body" in attrs and not _is_skip_marker(body):
        size = attrs.get("request_body_size")
        size = size if isinstance(size, int) else None
        kept = attrs.get("request_body_kept")
        if any(path.startswith(p) for p in prefixes):
            attrs["request_body"] = skipped_body("path_skipped", size)
        elif isinstance(body, dict) and isinstance(kept, list):
            fields = {str(f) for f in kept}
            attrs["request_body"] = {
                k: _redact(v) for k, v in body.items() if k in fields and not is_sensitive(k)
            }
        else:
            attrs["request_body"] = skipped_body("not_recorded", size)
    query = attrs.get("query_params")
    if isinstance(query, dict):
        attrs["query_params"] = _redact_pairs(query.items())
    return attrs


# The account an anonymous request is recorded under: Nexus's own.
ANONYMOUS_REQUEST_ACCOUNT = "api"


class HttpActivityLogMiddleware:
    """Pure-ASGI middleware: records one ``http.request`` event per request.

    Reads the ActivityLog service from ``scope['app'].state.activity_log_service``.
    If the service is absent, requests pass through untouched.
    """

    def __init__(
        self,
        app: ASGIApp,
        max_body_bytes: int = DEFAULT_MAX_BODY_BYTES,
        skip_body_path_prefixes: tuple[str, ...] = DEFAULT_SKIP_BODY_PATH_PREFIXES,
        capture_request_body: bool = True,
        skip_record_paths: frozenset[str] = DEFAULT_SKIP_RECORD_PATHS,
    ) -> None:
        self.app = app
        self.skip_record_paths = frozenset(skip_record_paths)
        self.max_body_bytes = max_body_bytes
        self.skip_body_path_prefixes = tuple(skip_body_path_prefixes)
        self.capture_request_body = capture_request_body

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope.get("path", "") in self.skip_record_paths:
            await self.app(scope, receive, send)
            return

        t0 = time.perf_counter()
        headers = Headers(scope=scope)
        path: str = scope.get("path", "")
        content_type = headers.get("content-type", "")
        content_length_header = headers.get("content-length")

        # Kept only for a JSON body: whether its route keeps any of it is known
        # once routing has run (``scope["route"]``).
        should_capture_body = (
            self.capture_request_body
            and not any(path.startswith(p) for p in self.skip_body_path_prefixes)
            and _is_json(content_type)
        )

        body_buf = bytearray()
        body_total = 0
        body_truncated = False
        body_skipped_reason: str | None = None
        if not self.capture_request_body:
            body_skipped_reason = "disabled"
        elif content_type.lower().startswith("multipart/form-data"):
            body_skipped_reason = "multipart"
        elif any(path.startswith(p) for p in self.skip_body_path_prefixes):
            body_skipped_reason = "path_skipped"
        elif not _is_json(content_type):
            body_skipped_reason = "not_recorded"

        async def receive_wrapper() -> Message:
            nonlocal body_total, body_truncated
            message = await receive()
            if should_capture_body and message["type"] == "http.request":
                chunk: bytes = message.get("body", b"") or b""
                if chunk:
                    body_total += len(chunk)
                    remaining = self.max_body_bytes - len(body_buf)
                    if remaining > 0:
                        body_buf.extend(chunk[:remaining])
                    if body_total > self.max_body_bytes:
                        body_truncated = True
            return message

        response_status = 500  # default if no response.start ever fires

        async def send_wrapper(message: Message) -> None:
            nonlocal response_status
            if message["type"] == "http.response.start":
                response_status = int(message.get("status", 500))
            await send(message)

        exc: BaseException | None = None
        try:
            await self.app(scope, receive_wrapper, send_wrapper)
        except BaseException as raised:
            exc = raised
            raise
        finally:
            duration_ms = int((time.perf_counter() - t0) * 1000)
            try:
                service = self._resolve_service(scope)
                if service is not None:
                    attrs = self._build_attributes(
                        scope=scope,
                        headers=headers,
                        status_code=response_status,
                        duration_ms=duration_ms,
                        body_buf=bytes(body_buf),
                        body_total=body_total,
                        body_truncated=body_truncated,
                        body_skipped_reason=body_skipped_reason,
                        content_type=content_type,
                        content_length_header=content_length_header,
                    )
                    view = current_view()
                    viewer = (scope.get("state") or {}).get("nexus_viewer")
                    if view is not None and viewer is not None:
                        attrs["view_as"] = {
                            "principal_id": view.person_principal_id,
                            "workspace_id": view.workspace_id,
                        }
                    else:
                        viewer = None
                    if exc is not None:
                        attrs["error"] = type(exc).__name__
                    # record() is a blocking call (it may cross the bus): keep it
                    # off the event loop so a slow log cannot stall every request.
                    # to_thread copies the context, so the caller's identity follows.
                    await asyncio.to_thread(self._record, service, headers, attrs, viewer)
            except Exception:
                # Activity logging must never break the request path.
                pass

    @staticmethod
    def _record(
        service: ActivityLogService,
        headers: Headers,
        attrs: dict[str, Any],
        viewer: Principal | None = None,
    ) -> None:
        def record() -> None:
            # The service names the actor from the call; this is its fallback
            # for a log not wired with IAM.
            service.record(
                ActivityEvent(
                    actor_id=call_actor() or ANONYMOUS_REQUEST_ACCOUNT,
                    event_type="http.request",
                    correlation_id=headers.get("x-request-id"),
                    attributes=attrs,
                )
            )

        if viewer is not None:
            # During a view the call is the person's, but the request is the viewer's act:
            # the event names the viewer, and the person only as an attribute.
            with use_call_context(replace(current_call_context(), on_behalf_of=viewer)):
                record()
            return
        if current_call_context().principal.kind != "anonymous":
            record()
            return
        attrs["anonymous"] = True
        with as_service_account(ANONYMOUS_REQUEST_ACCOUNT):
            record()

    @staticmethod
    def _resolve_service(scope: Scope) -> ActivityLogService | None:
        app = scope.get("app")
        if app is None:
            return None
        state = getattr(app, "state", None)
        if state is None:
            return None
        return getattr(state, "activity_log_service", None)

    def _build_attributes(
        self,
        *,
        scope: Scope,
        headers: Headers,
        status_code: int,
        duration_ms: int,
        body_buf: bytes,
        body_total: int,
        body_truncated: bool,
        body_skipped_reason: str | None,
        content_type: str,
        content_length_header: str | None,
    ) -> dict[str, Any]:
        client = scope.get("client")
        client_ip = client[0] if client else None

        query_string: bytes = scope.get("query_string", b"") or b""
        query_params: dict[str, str] | None = None
        if query_string:
            try:
                query_params = _redact_pairs(
                    parse_qsl(query_string.decode("latin-1"), keep_blank_values=True)
                )
            except Exception:
                query_params = None

        attrs: dict[str, Any] = {
            "method": scope.get("method"),
            # A remote app's path holds its grant, a bearer credential.
            "path": redact_grant_path(scope.get("path") or ""),
            "status_code": status_code,
            "duration_ms": duration_ms,
            "ip": client_ip,
            "user_agent": headers.get("user-agent"),
            "has_auth_header": headers.get("authorization") is not None,
            "content_type": content_type or None,
        }
        if query_params is not None:
            attrs["query_params"] = query_params

        if body_skipped_reason is not None:
            try:
                size_hint = int(content_length_header) if content_length_header else None
            except ValueError:
                size_hint = None
            if body_skipped_reason != "not_recorded" or size_hint:
                attrs["request_body"] = skipped_body(body_skipped_reason, size_hint)
        elif body_total > 0:
            fields = recorded_fields(scope.get("route"))
            kept = _kept_body(body_buf, fields) if fields and not body_truncated else None
            if kept is None:
                attrs["request_body"] = skipped_body("not_recorded", body_total)
            else:
                attrs["request_body"] = kept
                attrs["request_body_size"] = body_total
                # What the route let the log keep: read back by ``redact_recorded``.
                attrs["request_body_kept"] = sorted(fields or ())

        return attrs
