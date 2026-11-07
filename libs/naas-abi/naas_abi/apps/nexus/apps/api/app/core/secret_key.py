"""The key that encrypts workspace secrets (and the provider tokens of sessions).

Nexus signs no token: ``secret_key`` used to sign them and to encrypt the
secrets, and now it does neither. Encryption has a key of its own,
``secrets_encryption_key``; when none is configured one is generated and persisted
through the engine secret store (``.env`` with the dotenv adapter) so it survives
restarts. What was encrypted under the old key moves to the new one at start
(``legacy_secret_keys`` names the keys to try).
"""

from __future__ import annotations

import logging
import secrets
from typing import Any, Protocol

SECRETS_KEY_NAME = "NEXUS_SECRETS_KEY"
# The name the old signing key was persisted under when it was generated.
LEGACY_SECRET_KEY_NAME = "SECRET_KEY"

# Values shipped as defaults or examples. Anyone can derive a key from them.
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


def resolve_secrets_key(configured: str, store: SecretStore) -> str:
    """The secrets key: configured, else stored, else generated and persisted."""
    if not is_insecure_secret_key(configured):
        return configured

    stored = store.get(SECRETS_KEY_NAME)
    if stored and not is_insecure_secret_key(str(stored)):
        return str(stored)

    generated = secrets.token_urlsafe(64)
    store.set(SECRETS_KEY_NAME, generated)
    if store.get(SECRETS_KEY_NAME) != generated:
        raise RuntimeError(
            f"No {SECRETS_KEY_NAME} is configured and the generated one could not be "
            f"persisted through the secret store. Set {SECRETS_KEY_NAME} in the "
            'environment (python -c "import secrets; print(secrets.token_urlsafe(64))").'
        )
    logger.info(
        "No %s was configured; generated one and stored it in the secret store.",
        SECRETS_KEY_NAME,
    )
    return generated


def legacy_secret_keys(configured: str, store: SecretStore) -> list[str]:
    """The keys data may still be encrypted under from before the secrets key: the
    old ``secret_key`` as configured, as an earlier start persisted it, and the
    published defaults (a deployment that never set one). Never empty strings."""
    found: list[str] = []
    stored = store.get(LEGACY_SECRET_KEY_NAME)
    for key in (configured, str(stored) if stored else "", *sorted(INSECURE_SECRET_KEYS)):
        key = key.strip()
        if key and key not in found:
            found.append(key)
    return found
