"""Grants for ``/app-remote/<grant>/<module_id>/<app>/<path>``.

A remote module's page runs sandboxed in an opaque origin, so the browser sends
it no cookie: the grant rides in the URL path, and relative URLs carry it. The
module's own JavaScript can read it, so it must never work as a session token:

* it is signed with a key derived from the API secret, never the secret
  itself, so ``decode_token`` (sessions, WebSocket, gateway) rejects it;
* it carries no ``sub``: the user id is ``uid``;
* it opens one app of one module, as one user, in one workspace (``ws``),
  until it expires or the user logs out (``revocation.py``: ``iat`` is when it
  was issued).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from urllib.parse import unquote_plus

from jose import JWTError, jwt

GRANT_SCOPE = "app-remote"
GRANT_ROUTE_PREFIX = "/app-remote"
_ALGORITHM = "HS256"
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
    issued_at: datetime | None = None


def grant_key(secret: str) -> str:
    """The key grants are signed with, derived from Nexus's ``secret``."""
    return hashlib.sha256(f"{secret}:{GRANT_SCOPE}".encode()).hexdigest()


def is_segment(module_id: str, app: str) -> bool:
    """Both name one URL segment each: no "/", "?", "#", "%" or dot segment."""
    return bool(re.fullmatch(MODULE_ID_PATTERN, module_id) and re.fullmatch(APP_NAME_PATTERN, app))


def mint_remote_app_grant(
    *,
    secret: str,
    user_id: str,
    module_id: str,
    app: str,
    minutes: int = 60,
    not_after: datetime | None = None,
    workspace_id: str = "",
) -> str:
    """A grant for one user; it never outlives ``not_after`` (the credential
    it was exchanged for)."""
    if not user_id:
        raise ValueError("a remote app grant needs a user")
    now = datetime.now(UTC)
    expires = now + timedelta(minutes=max(1, min(minutes, 24 * 60)))
    if not_after is not None:
        expires = min(expires, not_after)
    claims = {
        "scope": GRANT_SCOPE,
        "uid": user_id,
        "mod": module_id,
        "app": app,
        "ws": workspace_id,
        # Fractional: a logout just before it must not end it (revocation.py).
        "iat": now.timestamp(),
        "exp": expires,
    }
    return jwt.encode(claims, grant_key(secret), algorithm=_ALGORITHM)


def read_remote_app_grant(token: str, *, secret: str) -> RemoteAppGrant | None:
    try:
        claims = jwt.decode(token, grant_key(secret), algorithms=[_ALGORITHM])
    except JWTError:
        return None
    if claims.get("scope") != GRANT_SCOPE or "sub" in claims:
        return None
    uid, module_id, app = claims.get("uid"), claims.get("mod"), claims.get("app")
    workspace_id, issued = claims.get("ws", ""), claims.get("iat")
    if not all(isinstance(v, str) for v in (uid, module_id, app, workspace_id)):
        return None
    if not (uid and module_id and app):
        return None
    if isinstance(issued, bool) or not isinstance(issued, int | float):
        return None
    return RemoteAppGrant(
        user_id=uid,
        module_id=module_id,
        app=app,
        workspace_id=workspace_id,
        issued_at=datetime.fromtimestamp(issued, UTC),
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
