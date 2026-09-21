"""Tokens for ``/app-preview/<token>/<path>``.

The token sits in the preview URL, where the previewed app's own JavaScript
can read it. So it must never work as a session token:

* it is signed with a key derived from the API secret, never the secret
  itself, so ``decode_token`` (sessions, WebSocket, gateway) rejects it;
* it carries no ``sub``: the user id is ``uid``;
* it grants one thing: reading one project's draft until it expires.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt

PREVIEW_SCOPE = "app-preview"
_ALGORITHM = "HS256"


@dataclass(frozen=True)
class PreviewGrant:
    user_id: str
    workspace_id: str
    slug: str


def _key(secret: str) -> str:
    return hashlib.sha256(f"{secret}:{PREVIEW_SCOPE}".encode()).hexdigest()


def mint_preview_token(
    *, secret: str, user_id: str, workspace_id: str, slug: str, minutes: int = 60
) -> str:
    claims = {
        "scope": PREVIEW_SCOPE,
        "uid": user_id,
        "ws": workspace_id,
        "slug": slug,
        "exp": datetime.now(UTC) + timedelta(minutes=max(1, min(minutes, 24 * 60))),
    }
    return jwt.encode(claims, _key(secret), algorithm=_ALGORITHM)


def read_preview_token(token: str, *, secret: str) -> PreviewGrant | None:
    try:
        claims = jwt.decode(token, _key(secret), algorithms=[_ALGORITHM])
    except JWTError:
        return None
    if claims.get("scope") != PREVIEW_SCOPE or "sub" in claims:
        return None
    uid, ws, slug = claims.get("uid"), claims.get("ws"), claims.get("slug")
    if not (isinstance(uid, str) and isinstance(ws, str) and isinstance(slug, str)):
        return None
    if not (uid and ws and slug):
        return None
    return PreviewGrant(user_id=uid, workspace_id=ws, slug=slug)
