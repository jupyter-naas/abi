from __future__ import annotations

import base64
import hashlib
from collections.abc import Iterable

from cryptography.fernet import Fernet, InvalidToken
from naas_abi.apps.nexus.apps.api.app.core.config import current_secret_key


def _fernet_for(secret_key: str) -> Fernet:
    key_hash = hashlib.sha256(secret_key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(key_hash))


def get_fernet() -> Fernet:
    return _fernet_for(current_secret_key())


def encrypt_secret_value(value: str) -> str:
    return get_fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret_value(encrypted_value: str) -> str:
    return get_fernet().decrypt(encrypted_value.encode("utf-8")).decode("utf-8")


def try_decrypt_secret_value(encrypted_value: str) -> str | None:
    try:
        return decrypt_secret_value(encrypted_value)
    except (InvalidToken, Exception):
        return None


def reencrypt_secret_value(encrypted_value: str, old_secret_keys: Iterable[str]) -> str | None:
    """Return ``encrypted_value`` re-encrypted under the current key.

    ``None`` when it is already readable with the current key, or when none of
    ``old_secret_keys`` can open it.
    """
    if try_decrypt_secret_value(encrypted_value) is not None:
        return None
    token = encrypted_value.encode("utf-8")
    for old_key in old_secret_keys:
        try:
            plaintext = _fernet_for(old_key).decrypt(token).decode("utf-8")
        except InvalidToken:
            continue
        return encrypt_secret_value(plaintext)
    return None
