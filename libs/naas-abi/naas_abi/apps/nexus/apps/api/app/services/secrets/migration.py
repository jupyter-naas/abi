"""Moving what ``secret_key`` encrypted under the secrets key (RFC §13).

Before, one key signed Nexus's tokens and encrypted the workspace secrets. It signs
nothing now and the encryption has a key of its own (``core/secret_key.py``): at
start, every ciphertext still under an old key (the old ``secret_key`` as
configured or persisted, the published defaults) is re-encrypted under the
current one. A value no known key opens is left as it is and counted, so setting
the old ``SECRET_KEY`` again moves it at the next start.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from naas_abi.apps.nexus.apps.api.app.models import AuthSessionModel, SecretModel
from naas_abi.apps.nexus.apps.api.app.services.secrets_crypto import (
    reencrypt_secret_value,
    try_decrypt_secret_value,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class KeyMove:
    secrets: int = 0
    session_tokens: int = 0
    # Ciphertexts no known key opens.
    unreadable: int = 0


def _moved(value: str | None, old_keys: Sequence[str]) -> tuple[str | None, bool]:
    """``(new ciphertext or None, readable)``: None when it is already under the
    current key, or when nothing opens it."""
    if not value:
        return None, True
    rotated = reencrypt_secret_value(value, old_keys)
    if rotated is not None:
        return rotated, True
    return None, try_decrypt_secret_value(value) is not None


async def move_to_secrets_key(db: AsyncSession, old_keys: Sequence[str]) -> KeyMove:
    """Re-encrypt workspace secrets and the provider tokens of sessions. The
    caller commits."""
    secrets_moved = tokens_moved = unreadable = 0
    for secret in (await db.execute(select(SecretModel))).scalars():
        rotated, readable = _moved(secret.encrypted_value, old_keys)
        if rotated is not None:
            secret.encrypted_value = rotated
            secrets_moved += 1
        elif not readable:
            unreadable += 1
    for session in (await db.execute(select(AuthSessionModel))).scalars():
        for column in ("refresh_token_enc", "id_token_enc"):
            rotated, readable = _moved(getattr(session, column), old_keys)
            if rotated is not None:
                setattr(session, column, rotated)
                tokens_moved += 1
            elif not readable:
                unreadable += 1
    await db.flush()
    return KeyMove(secrets_moved, tokens_moved, unreadable)
