"""Pure-ASGI HTTP activity-log middleware (Sentry-style).

Wraps the downstream ASGI app to:
- accumulate request body chunks as they stream in (capped + redacted),
- observe the response status,
- record one ``http.request`` ActivityEvent per request,
without disrupting the downstream handler.

Lives in Nexus rather than naas-abi-core because it bridges two
domains core knows nothing about:
- "what is a user?" (Nexus auth JWT → ``actor_id``)
- "what is an HTTP request?" (ASGI)
"""

from __future__ import annotations

import base64
import json
import time
from typing import Any, Iterable
from urllib.parse import parse_qsl

from naas_abi_core.services.activity_log.ActivityLogPort import ActivityEvent
from naas_abi_core.services.activity_log.ActivityLogService import ActivityLogService
from starlette.datastructures import Headers
from starlette.types import ASGIApp, Message, Receive, Scope, Send


# Sentry-style denylist. Keys are matched case-insensitively against any
# JSON object key, form key, or query parameter name.
SENSITIVE_KEYS: frozenset[str] = frozenset(
    {
        "password",
        "passwd",
        "secret",
        "api_key",
        "apikey",
        "token",
        "access_token",
        "refresh_token",
        "auth",
        "authorization",
        "credentials",
        "private_key",
        "csrf",
        "session",
    }
)

REDACTED = "[REDACTED]"

DEFAULT_MAX_BODY_BYTES = 64 * 1024  # 64 KB
DEFAULT_SKIP_BODY_PATH_PREFIXES: tuple[str, ...] = ("/api/auth/",)


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            k: (REDACTED if k.lower() in SENSITIVE_KEYS else _redact(v))
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [_redact(v) for v in value]
    return value


def _redact_pairs(pairs: Iterable[tuple[str, str]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in pairs:
        out[k] = REDACTED if k.lower() in SENSITIVE_KEYS else v
    return out


def _decode_body(raw: bytes, content_type: str) -> Any:
    """Best-effort body normalization with redaction.

    Returns one of:
    - a dict (JSON, redacted),
    - a dict of form fields (urlencoded, redacted),
    - a str (plain text),
    - a dict {"_b64": <base64>} for binary that didn't decode.
    """
    ct = content_type.split(";", 1)[0].strip().lower()

    if ct == "application/json" or ct.endswith("+json"):
        try:
            return _redact(json.loads(raw.decode("utf-8")))
        except (UnicodeDecodeError, json.JSONDecodeError):
            pass

    if ct == "application/x-www-form-urlencoded":
        try:
            decoded = raw.decode("utf-8")
            return _redact_pairs(parse_qsl(decoded, keep_blank_values=True))
        except UnicodeDecodeError:
            pass

    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return {"_b64": base64.b64encode(raw).decode("ascii")}


def _resolve_actor_id_from_headers(headers: Headers) -> str:
    auth = headers.get("authorization")
    if not auth:
        return "anonymous"
    parts = auth.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return "anonymous"
    token = parts[1].strip()
    if not token:
        return "anonymous"
    try:
        from naas_abi.apps.nexus.apps.api.app.services.auth.service import decode_token

        payload = decode_token(token)
    except Exception:
        return "anonymous"
    if not payload:
        return "anonymous"
    sub = payload.get("sub")
    if not sub:
        return "anonymous"
    return f"user:{sub}"


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
    ) -> None:
        self.app = app
        self.max_body_bytes = max_body_bytes
        self.skip_body_path_prefixes = tuple(skip_body_path_prefixes)
        self.capture_request_body = capture_request_body

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        t0 = time.perf_counter()
        headers = Headers(scope=scope)
        path: str = scope.get("path", "")
        content_type = headers.get("content-type", "")
        content_length_header = headers.get("content-length")

        should_capture_body = (
            self.capture_request_body
            and not any(path.startswith(p) for p in self.skip_body_path_prefixes)
            and not content_type.lower().startswith("multipart/form-data")
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
                    actor_id = _resolve_actor_id_from_headers(headers)
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
                    if exc is not None:
                        attrs["error"] = type(exc).__name__

                    service.record(
                        ActivityEvent(
                            actor_id=actor_id,
                            event_type="http.request",
                            correlation_id=headers.get("x-request-id"),
                            attributes=attrs,
                        )
                    )
            except Exception:
                # Activity logging must never break the request path.
                pass

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
            "path": scope.get("path"),
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
                size_hint = (
                    int(content_length_header) if content_length_header else None
                )
            except ValueError:
                size_hint = None
            attrs["request_body"] = (
                f"[{body_skipped_reason.upper()}"
                + (f":{size_hint}" if size_hint is not None else "")
                + "]"
            )
        elif body_total > 0:
            decoded = _decode_body(body_buf, content_type)
            attrs["request_body"] = decoded
            attrs["request_body_size"] = body_total
            if body_truncated:
                attrs["request_body_truncated"] = True

        return attrs
