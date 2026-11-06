"""Set who and which workspace every API request acts for.

Each request runs with a ``CallContext`` (``naas_abi_core.engine.call_context``):
the ``api`` service account acting on behalf of the signed-in user. In process,
every kernel call Nexus makes for the request carries it directly; over NATS the
call carries a delegation naming ``api`` and the user (``engine_credentials``),
never a header. So the user is named only as strictly as the credential that
proves them (``services/auth/credentials.py``): a session, or an API key, a
coding agent's key where the route takes one, each not revoked and not
suspended. A link (app-html, preview, remote app grant), an agent delegation, a
revoked or unknown credential, or none, leaves the request ``ANONYMOUS``, not
``api``: a public route must never get ``api``'s rights.

A credential of a kind the route does not take (a coding key on ``/api/chat``,
an API key on ``/api/auth/*``) names nobody either, and is marked so
(``request.state.nexus_credential_refused``) for a 403. A key narrows the
context: its scope is the context's ``scope``, intersected with the user's own
policy.

Without a bearer token, the session cookie of a sign-in through an identity
provider names the user (``services/oidc``): its IAM principal id, with the
IAM groups its provider's groups claim maps to. A cookie request that changes
state without the session's CSRF token names nobody, and is marked so
(``request.state.nexus_csrf_failed``) for a 403. The session is left on
``request.state.nexus_session``.

Pure ASGI, so the context is set in the request's own context: async
endpoints, sync endpoints (Starlette copies the context into the threadpool)
and everything they await see it. ``EventService.publish()`` stamps the user
and the container (the workspace's) on every event, and identity event capture
uses the user for ``created_by``.

The workspace is the ``/workspaces/{id}`` path segment, else a
``workspace_id`` query parameter; the call is made in its container
(``CallContext.container``, ``abi:nexus:organization/<org>/nexus:workspace/<ws>``).
Handlers that learn the workspace from the body (chat) set ``agent_container``
themselves — a view of the same context.

**A view** (``services/view_as``): a cookie session with a running view makes the
request the person's, in the viewed workspace. The credential and the context become
the person's together (user id, ``on_behalf_of``, and the identity provider groups
the view recorded: IAM adds the stored ones), the call's container is the workspace's,
``nexus_session`` stays the viewer's, and the view and the viewer are left on the
request state (``nexus_view``, ``nexus_viewer``). ``iam:ViewAs`` is decided again at
every request; a view past its end is ended and the request is the viewer's. A bearer
credential never carries a view, and a view that cannot be verified names nobody
(``nexus_view_unavailable``). The view's read-only and workspace limits are
``services/view_as``'s ``ViewGuardMiddleware``. The view is also set for the request
(``view_as.active``: ``viewing()``), for the code that must do nothing, or answer nothing,
in a view (private content, page loads that write, the activity log, the links of apps).
"""

from __future__ import annotations

import logging
import re
from dataclasses import replace
from urllib.parse import parse_qs

from naas_abi.apps.nexus.apps.api.app.services.auth.credentials import (
    Credential,
    CredentialKind,
    accepted_kinds,
    bearer_credential,
)
from naas_abi.apps.nexus.apps.api.app.services.view_as.active import use_view
from naas_abi_core.engine.call_context import (
    ANONYMOUS,
    CallContext,
    Principal,
    service_account,
    use_call_context,
)
from naas_abi_core.services.iam.names import UNRESOLVED
from starlette.datastructures import Headers
from starlette.types import ASGIApp, Receive, Scope, Send

_log = logging.getLogger(__name__)
_WORKSPACE_PATH = re.compile(r"/workspaces/([^/?#]+)")
# The service account Nexus serves its requests as.
NEXUS_IDENTITY = "api"


def _bearer(headers: Headers) -> str | None:
    auth = headers.get("authorization") or ""
    scheme, _, token = auth.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


async def verified_credential(
    headers: Headers, path: str
) -> tuple[Credential | None, CredentialKind | None]:
    """The credential of a request's bearer token, checked as IAM checks a key
    or an engine token: ``(credential, None)``; or
    ``(None, kind)`` for a valid credential of a kind ``path`` does not take;
    or ``(None, None)``. Fails closed."""
    token = _bearer(headers)
    if token is None:
        return None, None
    credential = await bearer_credential(token)
    if credential is None:
        return None, None
    if credential.kind not in accepted_kinds(path):
        return None, credential.kind
    return credential, None


def workspace_id_from_request(path: str, query_string: bytes) -> str | None:
    match = _WORKSPACE_PATH.search(path)
    if match:
        return match.group(1)
    values = parse_qs(query_string.decode("latin-1")).get("workspace_id")
    return values[0] if values and values[0] else None


class RequestIdentityMiddleware:
    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        # Websockets too (Socket.IO): their handlers run in this context.
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        context = await request_call_context(scope)
        view = (scope.get("state") or {}).get("nexus_view")
        with use_call_context(context), use_view(view):
            await self.app(scope, receive, send)


async def _workspace_container(workspace_id: str | None) -> str | None:
    """The container of the workspace a request names, as IAM registered it: the
    call is made in it. None for no workspace, or no IAM; ``names.UNRESOLVED``
    for a workspace IAM does not know (a deleted one), so what the call creates
    is not found rather than placed on the platform (request data, never
    identity: IAM checks it again before it names anything)."""
    from naas_abi.apps.nexus.apps.api.app.services.iam.names import (
        RESERVED_WORKSPACE_IDS,
    )
    from naas_abi.apps.nexus.apps.api.app.services.iam.runtime import IAMUnavailableError

    if not workspace_id or workspace_id in RESERVED_WORKSPACE_IDS:
        return None
    from naas_abi.apps.nexus.apps.api.app.services.iam.authz import AUTHZ

    try:
        found = await AUTHZ.container_of(workspace_id)
    except IAMUnavailableError:
        return None  # no IAM: the call is made in no container, and decides nothing
    except Exception:  # noqa: BLE001 - unreadable: named nowhere, never wider
        _log.warning("The container of workspace %s could not be read", workspace_id)
        return UNRESOLVED
    return found or UNRESOLVED


async def request_call_context(scope: Scope) -> CallContext:
    """``api`` on behalf of the request's verified user, narrowed by the scope of
    the credential that proved them; without one, ``ANONYMOUS`` (with the
    request's workspace and trigger)."""
    headers = Headers(scope=scope)
    state = scope.setdefault("state", {})
    credential, refused = await verified_credential(headers, scope.get("path", ""))
    if credential is not None:
        state["nexus_credential"] = credential
    elif refused is not None:
        state["nexus_credential_refused"] = refused
    cookie_session = None  # only a cookie session can carry a view
    if credential is None:
        from naas_abi.apps.nexus.apps.api.app.services.oidc.runtime import cookie_auth

        auth = await cookie_auth(scope)
        if auth is not None:
            if auth.session is not None:
                state["nexus_session"] = cookie_session = auth.session
                state.pop("nexus_credential_refused", None)
                credential = Credential(
                    kind="session",
                    user_id=auth.session.user_id,
                    groups=frozenset(auth.session.group_ids),
                    session=auth.session,
                )
                state["nexus_credential"] = credential
            elif auth.csrf_failed:
                state["nexus_csrf_failed"] = True
    view = None
    if credential is not None and cookie_session is not None and scope["type"] == "http":
        viewer = credential
        try:
            view = await _running_view(cookie_session)
        except Exception as exc:  # noqa: BLE001 - fail closed: the request names nobody
            _log.warning("A view could not be verified; the request names nobody: %s", exc)
            state["nexus_view_unavailable"] = True
            if not scope.get("path", "").startswith("/api/"):
                state.pop("nexus_credential", None)
            # The call names nobody; the viewer's own credential stays on the state of an
            # /api request only so Stop and the sign-out can end what they own: the guard
            # answers every other route 503 (``ViewGuardMiddleware``).
            credential = None
        else:
            if view is not None:
                # The person's, whole: user id, groups and (below) the call's container.
                credential = Credential(
                    kind="session",
                    user_id=view.person_id,
                    groups=frozenset(view.group_ids),
                    session=cookie_session,
                )
                state["nexus_credential"] = credential
                state["nexus_view"] = view
                state["nexus_viewer"] = Principal(
                    id=viewer.user_id, kind="user", groups=viewer.groups
                )
    named = (
        Principal(id=credential.user_id, kind="user", groups=credential.groups)
        if credential is not None
        else None
    )
    return replace(
        ANONYMOUS,
        principal=service_account(NEXUS_IDENTITY) if named else ANONYMOUS.principal,
        on_behalf_of=named,
        scope=credential.scope if credential is not None else None,
        container=view.container
        if view is not None
        else await _workspace_container(
            workspace_id_from_request(scope.get("path", ""), scope.get("query_string", b""))
        ),
        triggered_via="api",
    )


async def _running_view(session):
    """The view the cookie session runs, or None."""
    from naas_abi.apps.nexus.apps.api.app.services.view_as.runtime import running_view

    return await running_view(session)
