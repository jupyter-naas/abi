"""Per-project credentials written to a project's ``.env``.

ABI ships no default passwords or API keys. The local API key, the secret of the
client Nexus signs in to the built-in identity provider with, and the broker's
passwords are generated once per project and stored in ``.env``; a value that is
one of the defaults older versions wrote is replaced in place.

The seeded admin has no password: Nexus has no login of its own, and the admin
signs in at the built-in identity provider with the code it mails to
``ADMIN_EMAIL``.
"""

from __future__ import annotations

import secrets
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

# The account the project templates seed (``users:`` of the Nexus configuration).
ADMIN_EMAIL = "admin@example.com"
API_KEY = "ABI_API_KEY"
# The secret of the client ABI (Nexus, as a relying party) signs in to the
# built-in IdP with: read by the engine (identity.providers) and by the IdP
# module, which hashes it. Generated once per project.
IDP_CLIENT_SECRET = "ABI_IDP_CLIENT_SECRET"
# The broker's static users and the .env keys of their passwords: the engine's
# processes (engine), and the engine's auth callout responder (auth). Every
# other connection (modules, scripts) logs in with a service key and is
# admitted by the callout. Docker reads them in .deploy/docker/nats/nats.conf,
# `abi dev` writes them into its own nats.conf.
NATS_USERS = {"engine": "NATS_ENGINE_PASSWORD", "auth": "NATS_AUTH_PASSWORD"}
NATS_PASSWORDS = tuple(NATS_USERS.values())
# The seed of the account key the callout signs admitted users with, and its
# public half, which nats.conf names (auth_callout.issuer, $NATS_AUTH_CALLOUT_ISSUER).
NATS_CALLOUT_SEED = "NATS_AUTH_CALLOUT_SEED"
NATS_CALLOUT_ISSUER = "NATS_AUTH_CALLOUT_ISSUER"
_MIN_NATS_PASSWORD = 16

# Values older CLI versions wrote as the API key.
_SHIPPED_DEFAULTS = frozenset(
    v.casefold() for v in ("Admin1234!", "admin", "admin1234", "admin1234!", "abi")
)


def _is_shipped_default(value: str | None) -> bool:
    return (value or "").strip().casefold() in _SHIPPED_DEFAULTS


def _read(env_path: Path) -> list[str]:
    return (
        env_path.read_text(encoding="utf-8").splitlines() if env_path.exists() else []
    )


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


def ensure_api_key(env_path: Path) -> str:
    """Return ``ABI_API_KEY`` from ``.env``, generating it when missing or a default."""
    lines = _read(env_path)
    key = _value(lines, API_KEY)
    if key and not _is_shipped_default(key):
        return key
    key = secrets.token_urlsafe(32)
    _write(env_path, _set(lines, API_KEY, key))
    return key


def ensure_idp_client_secret(env_path: Path) -> str:
    """Return ``ABI_IDP_CLIENT_SECRET`` from ``.env``, generating it when missing."""
    lines = _read(env_path)
    secret = _value(lines, IDP_CLIENT_SECRET)
    if secret and len(secret) >= 24:
        return secret
    secret = secrets.token_urlsafe(32)
    _write(env_path, _set(lines, IDP_CLIENT_SECRET, secret))
    return secret


def ensure_nats_callout_seed(env_path: Path) -> str:
    """Return ``NATS_AUTH_CALLOUT_SEED`` from ``.env``, generating it when missing
    or not an account seed. Its public key is ``nats_callout_issuer(seed)``."""
    from naas_abi_core.engine.nats_nkeys import PREFIX_ACCOUNT, KeyPair, NKeyError

    lines = _read(env_path)
    original = list(lines)
    seed = _value(lines, NATS_CALLOUT_SEED) or ""
    try:
        pair = KeyPair.from_seed(seed)
        if pair.prefix != PREFIX_ACCOUNT:
            raise NKeyError("not an account seed")
    except NKeyError:
        pair = KeyPair.create(PREFIX_ACCOUNT)
        lines = _set(lines, NATS_CALLOUT_SEED, pair.seed)
    if _value(lines, NATS_CALLOUT_ISSUER) != pair.public_key:
        lines = _set(lines, NATS_CALLOUT_ISSUER, pair.public_key)
    if lines != original:
        _write(env_path, lines)
    return pair.seed


def nats_callout_issuer(seed: str) -> str:
    """The account public key nats.conf trusts as the callout's issuer."""
    from naas_abi_core.engine.nats_nkeys import KeyPair

    return KeyPair.from_seed(seed).public_key


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
