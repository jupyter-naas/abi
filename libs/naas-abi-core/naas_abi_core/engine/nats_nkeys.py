"""NATS nkeys and user JWTs, for the auth callout (RFC §8.4).

The broker's auth callout trusts one account key: ``nats.conf`` names its
public half (``auth_callout.issuer``), and the engine signs every user it
admits with the seed. An nkey is an ed25519 key in NATS's encoding: a type
prefix, the key, a CRC-16 (XMODEM), in base32. NATS JWTs are signed with
``ed25519-nkey``. Written on ``cryptography``, which core already needs.
"""

from __future__ import annotations

import base64
import json
import os
import time
from dataclasses import dataclass
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

PREFIX_SEED = 18 << 3
PREFIX_ACCOUNT = 0
PREFIX_SERVER = 13 << 3
PREFIX_USER = 20 << 3
_PREFIXES = {"A": PREFIX_ACCOUNT, "N": PREFIX_SERVER, "U": PREFIX_USER}


class NKeyError(ValueError):
    pass


def _crc16(data: bytes) -> int:
    crc = 0
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if crc & 0x8000 else crc << 1
            crc &= 0xFFFF
    return crc


def _encode(raw: bytes) -> str:
    raw += _crc16(raw).to_bytes(2, "little")
    return base64.b32encode(raw).decode().rstrip("=")


def _decode(text: str) -> bytes:
    try:
        raw = base64.b32decode(text + "=" * (-len(text) % 8))
    except (ValueError, TypeError) as exc:
        raise NKeyError("not an nkey") from exc
    if len(raw) < 3 or _crc16(raw[:-2]) != int.from_bytes(raw[-2:], "little"):
        raise NKeyError("nkey checksum mismatch")
    return raw[:-2]


def encode_public(prefix: int, key: bytes) -> str:
    return _encode(bytes([prefix]) + key)


def decode_public(text: str) -> tuple[int, bytes]:
    raw = _decode(text)
    if len(raw) != 33:
        raise NKeyError("not a public nkey")
    return raw[0], raw[1:]


@dataclass(frozen=True)
class KeyPair:
    """An nkey seed: signs, and names its public key."""

    prefix: int
    private: Ed25519PrivateKey

    @classmethod
    def create(cls, prefix: int = PREFIX_ACCOUNT) -> KeyPair:
        return cls(prefix, Ed25519PrivateKey.generate())

    @classmethod
    def from_seed(cls, seed: str) -> KeyPair:
        raw = _decode(seed.strip())
        if len(raw) != 34 or raw[0] & 0xF8 != PREFIX_SEED:
            raise NKeyError("not an nkey seed")
        prefix = ((raw[0] & 0x07) << 5) | ((raw[1] & 0xF8) >> 3)
        return cls(prefix, Ed25519PrivateKey.from_private_bytes(raw[2:]))

    @property
    def seed(self) -> str:
        raw = self.private.private_bytes(
            serialization.Encoding.Raw,
            serialization.PrivateFormat.Raw,
            serialization.NoEncryption(),
        )
        head = bytes([PREFIX_SEED | (self.prefix >> 5), (self.prefix & 0x1F) << 3])
        return _encode(head + raw)

    @property
    def public_key(self) -> str:
        raw = self.private.public_key().public_bytes(
            serialization.Encoding.Raw, serialization.PublicFormat.Raw
        )
        return encode_public(self.prefix, raw)

    def sign(self, data: bytes) -> bytes:
        return self.private.sign(data)


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


_HEADER = {"typ": "JWT", "alg": "ed25519-nkey"}


def encode_jwt(claims: dict[str, Any], signer: KeyPair) -> str:
    claims = {
        "jti": base64.b32encode(os.urandom(20)).decode().rstrip("="),
        "iat": int(time.time()),
        "iss": signer.public_key,
        **claims,
    }
    head = _b64(json.dumps(_HEADER, separators=(",", ":")).encode())
    body = _b64(json.dumps(claims, separators=(",", ":")).encode())
    signature = signer.sign(f"{head}.{body}".encode())
    return f"{head}.{body}.{_b64(signature)}"


def decode_jwt(token: str, *, issuer_prefix: int | None = None) -> dict[str, Any]:
    """The claims of a NATS JWT whose signature checks against its ``iss``."""
    try:
        head, body, signature = token.split(".")
        header = json.loads(_unb64(head))
        claims = json.loads(_unb64(body))
    except (ValueError, TypeError) as exc:
        raise NKeyError("malformed NATS JWT") from exc
    if header.get("alg") != "ed25519-nkey":
        raise NKeyError("not an ed25519-nkey JWT")
    prefix, key = decode_public(str(claims.get("iss", "")))
    if issuer_prefix is not None and prefix != issuer_prefix:
        raise NKeyError("unexpected JWT issuer kind")
    try:
        Ed25519PublicKey.from_public_bytes(key).verify(
            _unb64(signature), f"{head}.{body}".encode()
        )
    except Exception as exc:
        raise NKeyError("bad NATS JWT signature") from exc
    return claims
