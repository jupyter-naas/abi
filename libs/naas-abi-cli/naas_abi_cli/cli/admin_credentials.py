"""Per-project credentials written to a project's ``.env``.

ABI ships no default passwords or API keys. The seeded admin account and the
local API key are generated once per project and stored in ``.env``; a value
that is one of the defaults older versions wrote is replaced in place.
"""

from __future__ import annotations

import re
import secrets
from pathlib import Path

ADMIN_EMAIL = "admin@example.com"
_ADMIN_PREFIX = re.sub(r"[^A-Z0-9]", "_", ADMIN_EMAIL.upper())
# The keys the Nexus user seeder reads (``NEXUS_USER_<EMAIL_PREFIX>_*``).
ADMIN_EMAIL_KEY = f"NEXUS_USER_{_ADMIN_PREFIX}_EMAIL"
ADMIN_PASSWORD_KEY = f"NEXUS_USER_{_ADMIN_PREFIX}_PASSWORD"
# Written by older `abi deploy local` templates; nothing reads it any more.
_LEGACY_ADMIN_PASSWORD_KEY = "NEXUS_USER_ADMIN_PASSWORD"
API_KEY = "ABI_API_KEY"

# Values older CLI versions wrote. Mirrors the Nexus auth list in
# naas_abi/apps/nexus/apps/api/app/services/auth/default_passwords.py.
_SHIPPED_DEFAULTS = frozenset(
    v.casefold() for v in ("Admin1234!", "admin", "admin1234", "admin1234!", "abi")
)


def _is_shipped_default(value: str | None) -> bool:
    return (value or "").strip().casefold() in _SHIPPED_DEFAULTS


def generate_admin_password() -> str:
    return secrets.token_urlsafe(24)


def _read(env_path: Path) -> list[str]:
    return env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []


def _value(lines: list[str], key: str) -> str | None:
    for line in lines:
        if line.strip().startswith(f"{key}="):
            return line.split("=", 1)[1].strip()
    return None


def _set(lines: list[str], key: str, value: str) -> list[str]:
    """Replace ``key`` in place, or append it."""
    replaced = False
    out: list[str] = []
    for line in lines:
        if line.strip().startswith(f"{key}="):
            if not replaced:
                out.append(f"{key}={value}")
                replaced = True
            continue
        out.append(line)
    if not replaced:
        out.append(f"{key}={value}")
    return out


def _write(env_path: Path, lines: list[str]) -> None:
    env_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def ensure_admin_credentials(env_path: Path) -> tuple[str, str]:
    """Return ``(email, password)`` for the seeded admin, generating what is missing."""
    lines = _read(env_path)
    original = list(lines)

    email = _value(lines, ADMIN_EMAIL_KEY) or ADMIN_EMAIL
    lines = _set(lines, ADMIN_EMAIL_KEY, email)

    password = _value(lines, ADMIN_PASSWORD_KEY)
    if not password or _is_shipped_default(password):
        password = generate_admin_password()
        lines = _set(lines, ADMIN_PASSWORD_KEY, password)

    if _is_shipped_default(_value(lines, _LEGACY_ADMIN_PASSWORD_KEY)):
        lines = [
            line
            for line in lines
            if not line.strip().startswith(f"{_LEGACY_ADMIN_PASSWORD_KEY}=")
        ]

    if lines != original:
        _write(env_path, lines)
    return email, password


def ensure_api_key(env_path: Path) -> str:
    """Return ``ABI_API_KEY`` from ``.env``, generating it when missing or a default."""
    lines = _read(env_path)
    key = _value(lines, API_KEY)
    if key and not _is_shipped_default(key):
        return key
    key = secrets.token_urlsafe(32)
    _write(env_path, _set(lines, API_KEY, key))
    return key
