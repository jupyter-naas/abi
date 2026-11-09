"""Hashes for passwords, client secrets, opaque tokens and sign-in codes.

Passwords and client secrets use scrypt from the standard library (no extra
dependency). Opaque tokens (refresh tokens, authorization codes, session
cookies) are 256-bit random values, so a plain SHA-256 is enough. Sign-in codes
are six digits, which no hash protects from guessing: they are an HMAC under a
key held in the secret service, so a copy of the documents alone gives nothing.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets

_N, _R, _P = 2**14, 8, 1


def hash_secret(value: str) -> str:
    """``scrypt$<salt>$<hash>``, salted."""
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(value.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    return f"scrypt${_b64(salt)}${_b64(digest)}"


def verify_secret(value: str, stored: str) -> bool:
    try:
        kind, salt, digest = stored.split("$")
        if kind != "scrypt":
            return False
        candidate = hashlib.scrypt(
            value.encode(), salt=_unb64(salt), n=_N, r=_R, p=_P, dklen=32
        )
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(candidate, _unb64(digest))


def token_id(token: str) -> str:
    """The id a token is kept under: its SHA-256."""
    return hashlib.sha256(token.encode()).hexdigest()


def new_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def code_digest(key: bytes, email: str, code: str) -> str:
    """The HMAC of a sign-in code, bound to the address it was sent to."""
    message = f"{email}\0{code}".encode()
    return hmac.new(key, message, hashlib.sha256).hexdigest()


def equal(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))
