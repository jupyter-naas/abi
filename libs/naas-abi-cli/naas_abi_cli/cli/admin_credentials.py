"""Per-project credentials written to a project's ``.env``.

ABI ships no default passwords or API keys. The seeded admin account and the
local API key are generated once per project and stored in ``.env``; a value
that is one of the defaults older versions wrote is replaced in place.
"""

from __future__ import annotations

import re
import secrets
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

ADMIN_EMAIL = "admin@example.com"
_ADMIN_PREFIX = re.sub(r"[^A-Z0-9]", "_", ADMIN_EMAIL.upper())
# The keys the Nexus user seeder reads (``NEXUS_USER_<EMAIL_PREFIX>_*``).
ADMIN_EMAIL_KEY = f"NEXUS_USER_{_ADMIN_PREFIX}_EMAIL"
ADMIN_PASSWORD_KEY = f"NEXUS_USER_{_ADMIN_PREFIX}_PASSWORD"
# Written by older `abi deploy local` templates; nothing reads it any more.
_LEGACY_ADMIN_PASSWORD_KEY = "NEXUS_USER_ADMIN_PASSWORD"
API_KEY = "ABI_API_KEY"
NATS_SECRET = "NATS_JWT_SECRET"
# The broker's users and the .env keys of their passwords: the engine's process
# (abi), and the SDK modules joining it (module). Docker reads them in
# .deploy/docker/nats/nats.conf, `abi dev` writes them into its own nats.conf.
NATS_USERS = {"abi": "NATS_ABI_PASSWORD", "module": "NATS_MODULE_PASSWORD"}
NATS_PASSWORDS = tuple(NATS_USERS.values())
_MIN_NATS_PASSWORD = 16

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


def ensure_nats_secret(env_path: Path) -> str:
    """Return ``NATS_JWT_SECRET`` from ``.env``, generating it when missing or short.

    Signs the service tokens of the dev engine and of any module joining its NATS.
    """
    lines = _read(env_path)
    secret = _value(lines, NATS_SECRET)
    if secret and len(secret) >= 32:
        return secret
    secret = secrets.token_urlsafe(48)
    _write(env_path, _set(lines, NATS_SECRET, secret))
    return secret


def module_key_variable(name: str) -> str:
    """The ``.env`` key holding a module's key for Compose (``ABI_MODULE_KEY_<NAME>``)."""
    return "ABI_MODULE_KEY_" + re.sub(r"[^A-Z0-9]", "_", name.upper())


class MissingNatsSecret(ValueError):
    """``.env`` has no ``NATS_JWT_SECRET`` to derive a module key from."""


def ensure_module_key(env_path: Path, name: str, module_id: str) -> tuple[str, bool]:
    """Write the module key of ``module_id`` to ``.env`` under
    ``module_key_variable(name)``; return it, and whether it replaced a different
    one (a key derived from an older secret).

    The key is derived from the ``NATS_JWT_SECRET`` already in ``.env``, the one
    the engine signs with: a module signs its tokens with it, for its module id
    only, and never gets the secret itself
    (docs/adr/20261014_module-identities.md). Without one, MissingNatsSecret:
    a secret made up here would not be the engine's.
    """
    from naas_abi_core.engine.nats_auth import module_key

    lines = _read(env_path)
    secret = _value(lines, NATS_SECRET)
    if not secret:
        raise MissingNatsSecret(f"{env_path} has no {NATS_SECRET}")
    key = module_key(secret, module_id)
    variable = module_key_variable(name)
    previous = _value(lines, variable)
    if previous != key:
        _write(env_path, _set(lines, variable, key))
    return key, bool(previous) and previous != key


def generate_nats_password() -> str:
    """A broker password that nats.conf and a ``nats://`` URL take as is.

    nats-server reads ``$VAR`` in nats.conf as a config value, so a value that
    starts with a digit or ``-`` does not parse; clients pass it in
    ``nats://user:password@host``, so it holds only URL-safe characters.
    """
    return f"nats-{secrets.token_urlsafe(32)}"


def ensure_nats_passwords(env_path: Path) -> dict[str, str]:
    """Return the broker passwords from ``.env``, generating any missing or short.

    nats-server takes an empty ``$VAR`` as an empty password, which lets anyone
    in as that user.
    """
    lines = _read(env_path)
    original = list(lines)
    passwords: dict[str, str] = {}
    for key in NATS_PASSWORDS:
        password = _value(lines, key) or ""
        if len(password) < _MIN_NATS_PASSWORD:
            password = generate_nats_password()
            lines = _set(lines, key, password)
        passwords[key] = password
    if lines != original:
        _write(env_path, lines)
    return passwords


RABBITMQ_USER = "RABBITMQ_USER"
RABBITMQ_PASSWORD = "RABBITMQ_PASSWORD"


def ensure_rabbitmq_credentials(env_path: Path) -> tuple[str, str]:
    """Return ``(user, password)`` of the legacy RabbitMQ bus from ``.env``,
    generating what is missing or a shipped default."""
    lines = _read(env_path)
    original = list(lines)
    user = _value(lines, RABBITMQ_USER) or "abi"
    lines = _set(lines, RABBITMQ_USER, user)
    password = _value(lines, RABBITMQ_PASSWORD)
    if not password or _is_shipped_default(password):
        password = secrets.token_urlsafe(24)
        lines = _set(lines, RABBITMQ_PASSWORD, password)
    if lines != original:
        _write(env_path, lines)
    return user, password


def nats_login(url: str, user: str, password: str) -> str:
    """``url`` logged in as ``user``: nats-py reads ``user:password@`` from it."""
    parts = urlsplit(url)
    host = parts.hostname or ""
    if ":" in host:
        host = f"[{host}]"
    port = f":{parts.port}" if parts.port else ""
    return urlunsplit(parts._replace(netloc=f"{user}:{password}@{host}{port}"))
