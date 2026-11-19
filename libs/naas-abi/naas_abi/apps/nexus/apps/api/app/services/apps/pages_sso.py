"""HMAC tokens that let a Nexus session sign in to one module app's portal.

A token is for one app: it names it (``app``, the ``<module_path>:<app_dir>``
id), its ``aud`` is that app's hostname, and it is signed with that app's own
secret (``pages_sso_secrets``), which the operator shares with that portal
alone. An app without a secret gets no token.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import ipaddress
import json
import time
from collections.abc import Mapping
from urllib.parse import urlparse

PAGES_SSO_SCOPE = "pages-sso"

# The single secret every portal once shared, which both signed and verified.
LEGACY_PAGES_SSO_SECRET_ENV = "PAGES_SSO_SECRET"
MOVE_THE_SHARED_SECRET = (
    "No portal gets a token from it any more: move the secret under the portal's "
    'app id in pages_sso_secrets ({"<module_path>:<app_dir>": "<secret>"}, or the '
    "PAGES_SSO_SECRETS JSON), and give each portal its own secret."
)


def portal_secrets(raw: Mapping[str, str] | None) -> dict[str, str]:
    """``pages_sso_secrets`` without blank app ids or empty secrets."""
    out: dict[str, str] = {}
    for app_id, secret in (raw or {}).items():
        key = str(app_id or "").strip()
        value = str(secret or "").strip()
        if key and value:
            out[key] = value
    return out


def shared_secret_warning(environ: Mapping[str, str]) -> str | None:
    """What to say at start while the old ``PAGES_SSO_SECRET`` is still set, else None."""
    if not str(environ.get(LEGACY_PAGES_SSO_SECRET_ENV) or "").strip():
        return None
    return f"{LEGACY_PAGES_SSO_SECRET_ENV} is set and signs nothing. {MOVE_THE_SHARED_SECRET}"


def _b64url(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def mint_pages_sso_token(
    *,
    email: str,
    audience: str,
    app_id: str,
    secret: str,
    expires_seconds: int = 300,
) -> tuple[str, int]:
    """Return ``(token, expires_in_seconds)``.

    ``audience`` is the portal hostname, ``app_id`` the app the token is for and
    ``secret`` that app's own secret.
    """
    if not secret:
        raise ValueError("this app has no portal sign-in secret")
    app = (app_id or "").strip()
    if not app:
        raise ValueError("a portal sign-in token names its app")
    host = audience.strip().lower()
    if not host or "/" in host or ":" in host:
        raise ValueError("audience must be a hostname")
    lifetime = max(30, min(int(expires_seconds), 15 * 60))
    exp = int(time.time()) + lifetime
    payload = json.dumps(
        {
            "app": app,
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
    app_id: str | None = None,
) -> str | None:
    """Return the email when the token is valid for ``audience``, else None.

    With ``app_id``, the token's ``app`` claim must also be that app. Without it,
    the claim is not read, so a portal that checks only ``aud``, ``scope``,
    ``exp`` and ``email`` still accepts the token.
    """
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
    if not isinstance(payload, dict):
        return None
    if payload.get("scope") != PAGES_SSO_SCOPE:
        return None
    if str(payload.get("aud") or "").lower() != audience.strip().lower():
        return None
    if app_id is not None and payload.get("app") != app_id.strip():
        return None
    exp = payload.get("exp")
    if not isinstance(exp, int) or exp < int(time.time()):
        return None
    email = str(payload.get("email") or "").strip().lower()
    if "@" not in email:
        return None
    return email


def pages_sso_audiences(*urls: str | None) -> frozenset[str]:
    """Hostnames of the portal URLs a proof may name. The port is not part of it."""
    hosts: set[str] = set()
    for url in urls:
        if not url:
            continue
        hostname = (urlparse(url).hostname or "").strip().lower()
        if hostname:
            hosts.add(hostname)
    return frozenset(hosts)


def parse_dev_app_urls(raw: str | None) -> dict[str, str]:
    """``id=url`` pairs, comma-separated. The first ``=`` splits id from URL.

    Empty when unset. Callers pass an entry only for the app being opened, and
    only while Nexus is local. There is no built-in catalog id.
    """
    out: dict[str, str] = {}
    if not raw:
        return out
    for part in raw.split(","):
        trimmed = part.strip()
        eq = trimmed.find("=")
        if eq <= 0:
            continue
        app_id = trimmed[:eq].strip()
        target = trimmed[eq + 1 :].strip()
        if app_id and target:
            out[app_id] = target
    return out


def is_loopback_host(host: str | None) -> bool:
    """``localhost``, a ``*.localhost`` name or a loopback address."""
    name = (host or "").strip().lower().rstrip(".")
    if name.startswith("[") and name.endswith("]"):
        name = name[1:-1]
    if name == "localhost" or name.endswith(".localhost"):
        return True
    try:
        return ipaddress.ip_address(name).is_loopback
    except ValueError:
        return False


def dev_app_url(
    app_id: str,
    *,
    dev_app_urls: str | None,
    nexus_env: str | None,
    frontend_url: str | None,
) -> str | None:
    """The dev origin ``NEXUS_DEV_APP_URLS`` names for ``app_id`` on a local Nexus, else None.

    ``nexus_env`` is ``local`` by default on every install, deployed ones
    included, so it is not enough alone: the Nexus web app (``frontend_url``)
    must also be on a loopback host, which no deployed Nexus is.
    """
    if str(nexus_env or "").strip().lower() != "local":
        return None
    if not is_loopback_host(urlparse(frontend_url or "").hostname):
        return None
    return parse_dev_app_urls(dev_app_urls).get(app_id)
