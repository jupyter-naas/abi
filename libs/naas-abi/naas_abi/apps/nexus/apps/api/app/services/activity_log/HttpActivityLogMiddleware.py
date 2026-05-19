"""HTTP middleware that records one ActivityEvent per request.

Sits in Nexus rather than naas-abi-core because it bridges two domains
that core knows nothing about:
- "what is a user?" (Nexus auth: JWT, ``user.id``)
- "what is an HTTP request?" (Starlette)

The core ActivityLog service receives an opaque ``actor_id`` string.
"""

import time

from naas_abi_core.services.activity_log.ActivityLogPort import ActivityEvent
from naas_abi_core.services.activity_log.ActivityLogService import ActivityLogService
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp


def _extract_bearer_token(request: Request) -> str | None:
    auth = request.headers.get("Authorization") or request.headers.get("authorization")
    if not auth:
        return None
    parts = auth.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return None
    return parts[1].strip() or None


def _resolve_actor_id(request: Request) -> str:
    """Map a request to an opaque actor_id string.

    Returns ``"user:<sub>"`` for an authenticated Nexus JWT, ``"anonymous"``
    otherwise. JWT decoding is deferred until first use so this module
    stays importable in contexts where Nexus auth isn't configured.
    """
    token = _extract_bearer_token(request)
    if token is None:
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


class HttpActivityLogMiddleware(BaseHTTPMiddleware):
    """Record one ``http.request`` event per request.

    The middleware reads the ActivityLog service from ``app.state``
    (set by the engine wiring). If the service is absent, requests pass
    through untouched — logging is best-effort and never breaks the call.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        t0 = time.perf_counter()
        response: Response | None = None
        exc: BaseException | None = None
        try:
            response = await call_next(request)
            return response
        except BaseException as raised:
            # Record then re-raise so downstream error handlers still run.
            exc = raised
            raise
        finally:
            duration_ms = int((time.perf_counter() - t0) * 1000)
            service: ActivityLogService | None = getattr(
                request.app.state, "activity_log_service", None
            )
            if service is not None:
                try:
                    actor_id = _resolve_actor_id(request)
                    client_ip = request.client.host if request.client else None
                    status_code = response.status_code if response is not None else 500
                    attrs: dict = {
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": status_code,
                        "duration_ms": duration_ms,
                        "ip": client_ip,
                        "user_agent": request.headers.get("user-agent"),
                    }
                    if exc is not None:
                        attrs["error"] = type(exc).__name__
                    event = ActivityEvent(
                        actor_id=actor_id,
                        event_type="http.request",
                        correlation_id=request.headers.get("x-request-id"),
                        attributes=attrs,
                    )
                    service.record(event)
                except Exception:
                    # Belt-and-suspenders; ActivityLogService.record already
                    # swallows adapter errors.
                    pass
