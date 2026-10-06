"""Resolve the key that signs Nexus JWTs and encrypts workspace secrets.

A deployment that never configured a key must not fall back to a value that is
published in this repository. When no real key is configured, one is generated
and persisted through the engine secret store (``.env`` with the dotenv adapter)
so it survives restarts.
"""

from __future__ import annotations

import logging
import secrets
from typing import Any, Protocol

SECRET_KEY_NAME = "SECRET_KEY"

# Values shipped as defaults or examples. Anyone can sign tokens with them.
INSECURE_SECRET_KEYS = frozenset(
    {
        "",
        "change-me-in-production",
        "change-me-in-production-use-a-long-random-string",
        "secret",
        "password",
        "changeme",
    }
)

logger = logging.getLogger(__name__)


class SecretStore(Protocol):
    def get(self, key: str, default: Any = None) -> Any: ...

    def set(self, key: str, value: str) -> None: ...


def is_insecure_secret_key(key: str | None) -> bool:
    """True for known default keys only.

    Length is deliberately not checked: replacing an operator's own key would
    orphan every secret already encrypted under it.
    """
    return (key or "").strip() in INSECURE_SECRET_KEYS


def resolve_secret_key(configured: str, store: SecretStore) -> str:
    """Return a secure key: configured, else stored, else generated and persisted."""
    if not is_insecure_secret_key(configured):
        return configured

    stored = store.get(SECRET_KEY_NAME)
    if stored and not is_insecure_secret_key(str(stored)):
        return str(stored)

    generated = secrets.token_urlsafe(64)
    store.set(SECRET_KEY_NAME, generated)
    if store.get(SECRET_KEY_NAME) != generated:
        raise RuntimeError(
            f"No {SECRET_KEY_NAME} is configured and the generated one could not be "
            f"persisted through the secret store. Set {SECRET_KEY_NAME} in the "
            'environment (python -c "import secrets; print(secrets.token_urlsafe(64))").'
        )
    logger.warning(
        "No %s was configured; generated one and stored it in the secret store. "
        "Existing sessions signed with the old default key are no longer valid.",
        SECRET_KEY_NAME,
    )
    return generated
