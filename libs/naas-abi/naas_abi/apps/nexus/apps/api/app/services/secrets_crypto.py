from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from naas_abi.apps.nexus.apps.api.app.core.config import settings


def get_fernet() -> Fernet:
    key_hash = hashlib.sha256(settings.secret_key.encode("utf-8")).digest()
    fernet_key = base64.urlsafe_b64encode(key_hash)
    return Fernet(fernet_key)


def encrypt_secret_value(value: str) -> str:
    return get_fernet().encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret_value(encrypted_value: str) -> str:
    return get_fernet().decrypt(encrypted_value.encode("utf-8")).decode("utf-8")


def try_decrypt_secret_value(encrypted_value: str) -> str | None:
    try:
        return decrypt_secret_value(encrypted_value)
    except (InvalidToken, Exception):
        return None
