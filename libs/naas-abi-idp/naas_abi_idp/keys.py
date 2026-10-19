"""The provider's ES256 signing keys, and the key that protects sign-in codes.

The private half of every signing key is a secret under ``idp/signing-keys/``
and the key of the sign-in codes is ``idp/code-key``: the secret service seals
the whole ``idp/`` prefix to this module's service account, so not even
``api`` or ``engine`` reads them. The public half and the key's life
(``created_at``, ``retired_at``) are documents, which the JWKS is built from.

A key signs for ``rotation_days`` (30), then the next one takes over and the
old one stays published for a day, longer than any token it signed lives.
"""

from __future__ import annotations

import base64
import secrets
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from authlib.jose import JsonWebKey

from naas_abi_idp.models import KEYS
from naas_abi_idp.ports import DocumentStore, SecretStore

SIGNING_KEY_PREFIX = "idp/signing-keys/"
CODE_KEY = "idp/code-key"
# How long a retired key stays in the JWKS: far past the ten minutes a token lives.
RETIRED_KEPT_SECONDS = 24 * 3600
# How often a process rereads the key documents: another replica may have rotated.
REFRESH_SECONDS = 30.0


@dataclass(frozen=True)
class SigningKey:
    kid: str
    key: Any = None  # an authlib key holding the private half; None for a public one
    public: dict[str, Any] | None = None
    created_at: float = 0.0
    retired_at: float | None = None


class KeyRing:
    def __init__(
        self,
        store: DocumentStore,
        secrets_: SecretStore,
        *,
        rotation_days: int = 30,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._store, self._secrets = store, secrets_
        self._rotation = rotation_days * 86400
        self._clock = clock
        self._lock = threading.RLock()
        self._keys: dict[str, SigningKey] = {}
        self._read_at = float("-inf")
        self._code_key: bytes | None = None

    # -- signing ----------------------------------------------------------------

    def active(self) -> SigningKey:
        """The key that signs now: the newest one still in its rotation period."""
        with self._lock:
            self._refresh()
            now = self._clock()
            live = [
                k
                for k in self._keys.values()
                if k.retired_at is None and k.key is not None
            ]
            newest = max(live, key=lambda k: k.created_at, default=None)
            if newest is None or now - newest.created_at >= self._rotation:
                return self._rotate_locked()
            return newest

    def rotate(self) -> SigningKey:
        """Make a new key the signing one now (the old one is retired)."""
        with self._lock:
            self._refresh(force=True)
            return self._rotate_locked()

    def jwks(self) -> dict[str, Any]:
        """The public keys: the active one and the retired ones still kept."""
        with self._lock:
            self.active()
            now = self._clock()
            keys = [
                k
                for k in self._keys.values()
                if k.public is not None
                and (k.retired_at is None or now - k.retired_at < RETIRED_KEPT_SECONDS)
            ]
            keys.sort(key=lambda k: k.created_at, reverse=True)
            return {"keys": [k.public for k in keys]}

    def code_key(self) -> bytes:
        """The HMAC key of sign-in codes, created on first use."""
        with self._lock:
            if self._code_key is None:
                value = self._secrets.get(CODE_KEY)
                if value is None:
                    value = base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()
                    self._secrets.set(CODE_KEY, value)
                self._code_key = base64.urlsafe_b64decode(value)
            return self._code_key

    # -- storage ----------------------------------------------------------------

    def _rotate_locked(self) -> SigningKey:
        now = self._clock()
        generated = JsonWebKey.generate_key("EC", "P-256", is_private=True)
        kid = f"{time.strftime('%Y%m%d', time.gmtime(now))}-{secrets.token_hex(4)}"
        public = {
            **generated.as_dict(is_private=False),
            "kid": kid,
            "alg": "ES256",
            "use": "sig",
        }
        # The private half first: a published key whose secret is missing signs nothing.
        self._secrets.set(
            SIGNING_KEY_PREFIX + kid, generated.as_pem(is_private=True).decode()
        )
        self._store.create(
            KEYS,
            kid,
            {"kid": kid, "public": public, "created_at": now, "retired_at": None},
        )
        for old in list(self._keys.values()):
            if old.retired_at is None:
                self._retire(old.kid, now)
        self._read_at = float("-inf")
        self._refresh()
        return self._keys[kid]

    def _retire(self, kid: str, now: float) -> None:
        for _ in range(3):
            doc = self._store.get(KEYS, kid)
            if doc is None or doc.data.get("retired_at") is not None:
                return
            if self._store.replace(doc, KEYS, {**doc.data, "retired_at": now}):
                return

    def _refresh(self, *, force: bool = False) -> None:
        now = self._clock()
        if not force and now - self._read_at < REFRESH_SECONDS:
            return
        found: dict[str, SigningKey] = {}
        after = None
        while True:
            page = self._store.find(KEYS, limit=100, after=after)
            for doc in page.items:
                found[doc.id] = self._load(doc.data)
            after = page.cursor
            if after is None:
                break
        self._keys = found
        self._read_at = now

    def _load(self, data: dict[str, Any]) -> SigningKey:
        kid = data["kid"]
        known = self._keys.get(kid)
        key = known.key if known is not None else None
        if key is None and data.get("retired_at") is None:
            pem = self._secrets.get(SIGNING_KEY_PREFIX + kid)
            if pem is not None:
                key = JsonWebKey.import_key(
                    pem, {"kty": "EC", "kid": kid, "alg": "ES256", "use": "sig"}
                )
        return SigningKey(
            kid=kid,
            key=key,
            public=data["public"],
            created_at=float(data["created_at"]),
            retired_at=data.get("retired_at"),
        )
