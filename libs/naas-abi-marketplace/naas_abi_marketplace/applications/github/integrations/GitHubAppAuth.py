"""GitHub App JWT + installation access token helpers (ABI-wide)."""

from __future__ import annotations

import os
import time
from typing import Any

import httpx
from jose import jwt

GITHUB_API = "https://api.github.com"
GITHUB_APP_INSTALLATION_ID_KEY = "GITHUB_APP_INSTALLATION_ID"


def normalize_private_key(raw: str) -> str:
    """Accept PEM with literal newlines or ``\\n`` escapes from dotenv."""
    text = (raw or "").strip().strip('"').strip("'")
    if "\\n" in text and "\n" not in text:
        text = text.replace("\\n", "\n")
    return text.strip()


def app_credentials() -> tuple[str, str] | None:
    """Return ``(app_id, private_key_pem)`` when both are configured."""
    app_id = (os.environ.get("GITHUB_APP_ID") or "").strip()
    private_key = normalize_private_key(os.environ.get("GITHUB_APP_PRIVATE_KEY") or "")
    if not app_id or not private_key:
        return None
    if "BEGIN" not in private_key:
        return None
    return app_id, private_key


def app_slug() -> str | None:
    slug = (os.environ.get("GITHUB_APP_SLUG") or "").strip()
    if slug:
        return slug
    link = (os.environ.get("GITHUB_APP_PUBLIC_LINK") or "").strip().rstrip("/")
    if "/apps/" in link:
        return link.rsplit("/apps/", 1)[-1].strip() or None
    return None


def app_configured() -> bool:
    return app_credentials() is not None and bool(app_slug())


def read_installation_id() -> str | None:
    value = (os.environ.get(GITHUB_APP_INSTALLATION_ID_KEY) or "").strip()
    return value or None


def create_app_jwt(app_id: str, private_key: str, *, now: int | None = None) -> str:
    """Sign a short-lived JWT for GitHub App authentication."""
    ts = int(time.time() if now is None else now)
    payload = {
        "iat": ts - 60,
        "exp": ts + (9 * 60),
        "iss": app_id,
    }
    token = jwt.encode(payload, private_key, algorithm="RS256")
    if isinstance(token, bytes):
        return token.decode("utf-8")
    return str(token)


def _app_headers(token: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "naasai-abi",
    }


def create_installation_access_token_sync(installation_id: str) -> dict[str, Any]:
    """Mint an installation access token (sync; for agent boot)."""
    creds = app_credentials()
    if creds is None:
        raise RuntimeError(
            "GitHub App is not configured. Set GITHUB_APP_ID and GITHUB_APP_PRIVATE_KEY."
        )
    app_id, private_key = creds
    app_jwt = create_app_jwt(app_id, private_key)
    url = f"{GITHUB_API}/app/installations/{installation_id}/access_tokens"
    with httpx.Client(timeout=30.0) as client:
        response = client.post(url, headers=_app_headers(app_jwt))
        if response.status_code >= 400:
            raise RuntimeError(
                f"GitHub installation token failed ({response.status_code}): {response.text[:300]}"
            )
        return response.json()


async def create_installation_access_token(installation_id: str) -> dict[str, Any]:
    """Mint an installation access token (async)."""
    creds = app_credentials()
    if creds is None:
        raise RuntimeError(
            "GitHub App is not configured. Set GITHUB_APP_ID and GITHUB_APP_PRIVATE_KEY."
        )
    app_id, private_key = creds
    app_jwt = create_app_jwt(app_id, private_key)
    url = f"{GITHUB_API}/app/installations/{installation_id}/access_tokens"
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(url, headers=_app_headers(app_jwt))
        if response.status_code >= 400:
            raise RuntimeError(
                f"GitHub installation token failed ({response.status_code}): {response.text[:300]}"
            )
        return response.json()


async def fetch_installation(installation_id: str) -> dict[str, Any]:
    """Load installation metadata; raises if the App cannot see it."""
    creds = app_credentials()
    if creds is None:
        raise RuntimeError("GitHub App is not configured.")
    app_id, private_key = creds
    app_jwt = create_app_jwt(app_id, private_key)
    url = f"{GITHUB_API}/app/installations/{installation_id}"
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, headers=_app_headers(app_jwt))
        if response.status_code >= 400:
            raise RuntimeError(
                f"GitHub installation lookup failed ({response.status_code}): {response.text[:300]}"
            )
        return response.json()


def resolve_access_token(configured: str | None = None) -> str:
    """Prefer a fresh App installation token; fall back to configured PAT/OAuth token."""
    from naas_abi.config.dotenv_secrets import is_usable_secret_value

    installation_id = read_installation_id()
    if installation_id and app_credentials() is not None:
        payload = create_installation_access_token_sync(installation_id)
        token = str(payload.get("token") or "").strip()
        if token:
            os.environ["GITHUB_ACCESS_TOKEN"] = token
            return token

    if is_usable_secret_value(configured):
        return str(configured).strip()

    env_token = (os.environ.get("GITHUB_ACCESS_TOKEN") or "").strip()
    if is_usable_secret_value(env_token):
        return env_token

    raise RuntimeError(
        "No usable GitHub credentials. Install the NaasAI ABI GitHub App "
        "(or set GITHUB_ACCESS_TOKEN), then retry."
    )


def install_url(*, state: str | None = None) -> str:
    slug = app_slug()
    if not slug:
        raise RuntimeError(
            "GITHUB_APP_SLUG (or GITHUB_APP_PUBLIC_LINK) is required to build the install URL."
        )
    base = f"https://github.com/apps/{slug}/installations/new"
    if state:
        from urllib.parse import urlencode

        return f"{base}?{urlencode({'state': state})}"
    return base
