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
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt

GRANT_SCOPE = "app-remote"
GRANT_ROUTE_PREFIX = "/app-remote"
_ALGORITHM = "HS256"


@dataclass(frozen=True)
class RemoteAppGrant:
    user_id: str
    module_id: str
    app: str


def _key(secret: str) -> str:
    return hashlib.sha256(f"{secret}:{GRANT_SCOPE}".encode()).hexdigest()


def mint_remote_app_grant(
    *, secret: str, user_id: str, module_id: str, app: str, minutes: int = 60
) -> str:
    claims = {
        "scope": GRANT_SCOPE,
        "uid": user_id,
        "mod": module_id,
        "app": app,
        "exp": datetime.now(UTC) + timedelta(minutes=max(1, min(minutes, 24 * 60))),
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
    if not (module_id and app):
        return None
    return RemoteAppGrant(user_id=uid, module_id=module_id, app=app)


def grant_root(grant: str, module_id: str, app: str) -> str:
    """Where the browser sees the app: relative URLs below it keep the grant."""
    return f"{GRANT_ROUTE_PREFIX}/{grant}/{module_id}/{app}"
