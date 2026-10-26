"""Service-account and personal keys.

``abi_sk_<key id>_<secret>`` (service accounts), ``abi_pk_<key id>_<secret>``
(personal API keys) and ``abi_gk_<key id>_<secret>`` (the link grants of apps and
previews, all of a user's): the key id is 16 lowercase base32 characters, the
secret 32 random bytes in base64url without padding. IAM stores the key id and
``sha256(secret)``; a 256-bit secret needs no slow hash. Comparison is
constant-time.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
from dataclasses import dataclass, field

from naas_abi_core.engine.nats_auth import (
    GRANT_KEY_PREFIX,
    PERSONAL_KEY_PREFIX,
    SERVICE_KEY_PREFIX,
    parse_key,
)
from naas_abi_core.services.iam.IAMPorts import KeyKind

PREFIXES: dict[KeyKind, str] = {
    "service": SERVICE_KEY_PREFIX,
    "personal": PERSONAL_KEY_PREFIX,
    "grant": GRANT_KEY_PREFIX,
}
_KIND_OF_PREFIX: dict[str, KeyKind] = {v: k for k, v in PREFIXES.items()}
# Active keys a principal may hold at once: enough to rotate.
MAX_ACTIVE_KEYS = 5


@dataclass(frozen=True)
class NewKey:
    key_id: str
    secret_hash: str
    value: str = field(repr=False)  # the whole key, shown once


def generate_key(kind: KeyKind = "service") -> NewKey:
    key_id = base64.b32encode(os.urandom(10)).decode().lower()
    secret = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode()
    return NewKey(key_id, hash_secret(secret), f"{PREFIXES[kind]}{key_id}_{secret}")


def hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode()).hexdigest()


@dataclass(frozen=True)
class PresentedKey:
    kind: KeyKind
    key_id: str
    secret: str = field(repr=False)

    def matches(self, secret_hash: str) -> bool:
        return hmac.compare_digest(hash_secret(self.secret), secret_hash)


def parse(value: str) -> PresentedKey:
    """``ValueError`` for anything that is not an ABI key."""
    prefix, key_id, secret = parse_key(value)
    return PresentedKey(_KIND_OF_PREFIX[prefix], key_id, secret)
