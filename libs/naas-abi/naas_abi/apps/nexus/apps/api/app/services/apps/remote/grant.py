"""Grants for ``/app-remote/<grant>/<module_id>/<app>/<path>``.

A remote module's page runs sandboxed in an opaque origin, so the browser sends
it no cookie: the grant rides in the URL path, and relative URLs carry it. The
module's own JavaScript can read it, so it must never work as a session token:

* it is signed with a key derived from the API secret, never the secret
  itself, so ``decode_token`` (sessions, WebSocket, gateway) rejects it;
* it carries no ``sub``: the user id is ``uid``;
* it opens one app of one module, as one user, until it expires.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt

GRANT_SCOPE = "app-remote"
GRANT_ROUTE_PREFIX = "/app-remote"
_ALGORITHM = "HS256"
# URL segments: a module id (dots allowed, never "." or "..") and an app name.
MODULE_ID_PATTERN = r"^[A-Za-z0-9_-][A-Za-z0-9_.-]{0,127}$"
APP_NAME_PATTERN = r"^[A-Za-z0-9_-]{1,64}$"
_GRANT_IN_PATH = re.compile(rf"^{GRANT_ROUTE_PREFIX}/[^/]+")


@dataclass(frozen=True)
class RemoteAppGrant:
    user_id: str
    module_id: str
    app: str


def _key(secret: str) -> str:
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
) -> str:
    """A grant for one user; it never outlives ``not_after`` (the credential
    it was exchanged for)."""
    if not user_id:
        raise ValueError("a remote app grant needs a user")
    expires = datetime.now(UTC) + timedelta(minutes=max(1, min(minutes, 24 * 60)))
    if not_after is not None:
        expires = min(expires, not_after)
    claims = {
        "scope": GRANT_SCOPE,
        "uid": user_id,
        "mod": module_id,
        "app": app,
        "exp": expires,
    }
    return jwt.encode(claims, _key(secret), algorithm=_ALGORITHM)


def read_remote_app_grant(token: str, *, secret: str) -> RemoteAppGrant | None:
    try:
        claims = jwt.decode(token, _key(secret), algorithms=[_ALGORITHM])
    except JWTError:
        return None
    if claims.get("scope") != GRANT_SCOPE or "sub" in claims:
        return None
    uid, module_id, app = claims.get("uid"), claims.get("mod"), claims.get("app")
    if not (isinstance(uid, str) and isinstance(module_id, str) and isinstance(app, str)):
        return None
    if not (uid and module_id and app):
        return None
    return RemoteAppGrant(user_id=uid, module_id=module_id, app=app)


def grant_root(grant: str, module_id: str, app: str) -> str:
    """Where the browser sees the app: relative URLs below it keep the grant."""
    return f"{GRANT_ROUTE_PREFIX}/{grant}/{module_id}/{app}"


def redact_grant_path(path: str) -> str:
    """The path with its grant hidden, for logs and traces: the grant is a
    bearer credential."""
    return _GRANT_IN_PATH.sub(f"{GRANT_ROUTE_PREFIX}/[grant]", path)
