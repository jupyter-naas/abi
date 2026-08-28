"""HMAC tokens that let a Nexus session open an allowlisted Pages portal."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

PAGES_SSO_SCOPE = "pages-sso"


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def mint_pages_sso_token(
    *,
    email: str,
    audience: str,
    secret: str,
    expires_seconds: int = 300,
) -> tuple[str, int]:
    """Return ``(token, expires_in_seconds)``. ``audience`` is the portal hostname."""
    if not secret:
        raise ValueError("pages_sso_secret is not configured")
    host = audience.strip().lower()
    if not host or "/" in host or ":" in host:
        raise ValueError("audience must be a hostname")
    lifetime = max(30, min(int(expires_seconds), 15 * 60))
    exp = int(time.time()) + lifetime
    payload = json.dumps(
        {
            "aud": host,
            "email": email.strip().lower(),
            "exp": exp,
            "scope": PAGES_SSO_SCOPE,
        },
        separators=(",", ":"),
        sort_keys=True,
    )
    body = _b64url(payload.encode("utf-8"))
    sig = hmac.new(secret.encode("utf-8"), body.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{body}.{sig}", lifetime


def verify_pages_sso_token(
    token: str,
    *,
    secret: str,
    audience: str,
) -> str | None:
    """Return the email when the token is valid for ``audience``, else None."""
    if not token or not secret or not audience:
        return None
    parts = token.split(".")
    if len(parts) != 2:
        return None
    body, sig = parts
    expected = hmac.new(
        secret.encode("utf-8"),
        body.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, sig):
        return None
    pad = "=" * ((4 - len(body) % 4) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode(body + pad))
    except (ValueError, json.JSONDecodeError):
        return None
    if payload.get("scope") != PAGES_SSO_SCOPE:
        return None
    if str(payload.get("aud") or "").lower() != audience.strip().lower():
        return None
    exp = payload.get("exp")
    if not isinstance(exp, int) or exp < int(time.time()):
        return None
    email = str(payload.get("email") or "").strip().lower()
    if "@" not in email:
        return None
    return email
