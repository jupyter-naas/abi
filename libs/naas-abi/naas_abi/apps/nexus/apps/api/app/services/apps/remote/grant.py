"""Grants for ``/app-remote/<grant>/<module_id>/<app>/<path>``.

A remote module's page runs sandboxed in an opaque origin, so the browser sends
it no cookie: the grant rides in the URL path, and relative URLs carry it. The
module's own JavaScript can read it, so it must never work as a session token:
it is an IAM grant (``apps/links.py``), ``abi_gk_<id>_<secret>``, of the user who
opened the app,

* for the audience ``abi:delegated:app`` only, which no route that takes a
  session takes;
* bound to one app of one module in one workspace (``resource``: the workspace
  is its last segment, ``access.py``), and narrowed to ``discovery:OpenApp`` on
  the app (``scope``);
* stored hashed by IAM, eight hours at most, revocable, and ended with its owner.

The module gets the workspace with each request, never the grant.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import unquote_plus

from naas_abi.apps.nexus.apps.api.app.services.apps import links
from naas_abi_core.engine.nats_auth import APP_AUDIENCE

GRANT_SCOPE = "app-remote"
GRANT_ROUTE_PREFIX = "/app-remote"
# URL segments: a module id (dots allowed, never "." or "..") and an app name.
MODULE_ID_PATTERN = r"^[A-Za-z0-9_-][A-Za-z0-9_.-]{0,127}$"
APP_NAME_PATTERN = r"^[A-Za-z0-9_-]{1,64}$"
_GRANT_IN_PATH = re.compile(rf"^{GRANT_ROUTE_PREFIX}/[^/]+")
# Query parameters that carry a credential, matched case-insensitively: the
# app-html routes take ``?token=<JWT>``, OAuth callbacks a ``code``, presigned
# URLs a signature.
CREDENTIAL_QUERY_KEYS: frozenset[str] = frozenset(
    {
        "token",
        "access_token",
        "refresh_token",
        "id_token",
        "api_key",
        "apikey",
        "key",
        "password",
        "secret",
        "client_secret",
        "code",
        "session",
        "signature",
        "sig",
        "x-amz-credential",
        "x-amz-security-token",
        "x-amz-signature",
    }
)


@dataclass(frozen=True)
class RemoteAppGrant:
    user_id: str
    module_id: str
    app: str
    workspace_id: str = ""
    scope: tuple[dict, ...] | None = None


def is_segment(module_id: str, app: str) -> bool:
    """Both name one URL segment each: no "/", "?", "#", "%" or dot segment."""
    return bool(re.fullmatch(MODULE_ID_PATTERN, module_id) and re.fullmatch(APP_NAME_PATTERN, app))


def mint_remote_app_grant(
    *,
    user_id: str,
    module_id: str,
    app: str,
    minutes: int = 60,
    not_after: datetime | None = None,
    workspace_id: str = "",
) -> str:
    """A grant for one user to open one app in one workspace; it never outlives
    ``not_after`` (the credential it was exchanged for)."""
    if not user_id:
        raise ValueError("a remote app grant needs a user")
    if not is_segment(module_id, app):
        raise ValueError("a remote app grant names one module and one app")
    value, _ = links.mint_link(
        user_id=user_id,
        audience=APP_AUDIENCE,
        resource=links.remote_app_resource(module_id, app, workspace_id),
        scope=links.remote_app_scope(module_id, app),
        minutes=minutes,
        not_after=not_after,
        description=f"remote app: {module_id}/{app}"[:200],
    )
    return value


def read_remote_app_grant(token: str) -> RemoteAppGrant | None:
    """What a grant opens, for whom; None when IAM refuses it (unknown, revoked,
    expired, of another audience, its user suspended) or it is no remote app's."""
    link = links.open_link(token, APP_AUDIENCE)
    if link is None:
        return None
    prefix = f"{links.REMOTE_APP}/"
    if not link.resource.startswith(prefix):
        return None
    module_id, _, rest = link.resource.removeprefix(prefix).partition("/")
    app, _, workspace_id = rest.partition("/")
    if not is_segment(module_id, app):
        return None
    return RemoteAppGrant(
        user_id=link.user_id,
        module_id=module_id,
        app=app,
        workspace_id=workspace_id,
        scope=link.scope,
    )


def grant_root(grant: str, module_id: str, app: str) -> str:
    """Where the browser sees the app: relative URLs below it keep the grant."""
    return f"{GRANT_ROUTE_PREFIX}/{grant}/{module_id}/{app}"


def redact_grant_path(path: str) -> str:
    """The path with its grant hidden, for logs and traces: the grant is a
    bearer credential."""
    return _GRANT_IN_PATH.sub(f"{GRANT_ROUTE_PREFIX}/[grant]", path)


def redact_request_target(target: str) -> str:
    """A request's path and query, as an access log prints them, with the
    grant and every credential parameter's value hidden. The other
    parameters stay as sent."""
    path, sep, query = target.partition("?")
    path = redact_grant_path(path)
    if not sep:
        return path
    pairs = []
    for pair in query.split("&"):
        name, eq, _ = pair.partition("=")
        if eq and unquote_plus(name).lower() in CREDENTIAL_QUERY_KEYS:
            pair = f"{name}=[redacted]"
        pairs.append(pair)
    return f"{path}?{'&'.join(pairs)}"
