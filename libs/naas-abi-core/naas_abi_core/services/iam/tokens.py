"""The engine's token issuer: ES256 signing keys, their rotation and the JWKS.

RFC §9.1:

* a key is named ``<yyyymmdd>-<8 hex>``; its public half and its schedule are
  in the store (``SigningKeyRecord``), its private half in ``IAMSecrets`` at
  ``iam/signing-keys/<kid>``, sealed to ``engine``;
* keys rotate every ``rotation_days``: the next key is published at least
  ``PUBLISH_AHEAD`` before it signs, and a key stays published for
  ``RETIRE_AFTER`` after the next one took over (a token lives ten minutes);
* the JWKS names the issuer, ``urn:abi:engine:<install id>``, next to the keys.

Rotation is checked whenever a token is issued or the JWKS read: no timer.
"""

from __future__ import annotations

import base64
import threading
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from naas_abi_core import logger
from naas_abi_core.engine.nats_auth import (
    MAX_TOKEN_SECONDS,
    IssuedToken,
    SigningKey,
    TokenClaims,
    epoch,
    new_token_id,
    sign_token,
)
from naas_abi_core.services.iam.IAMPorts import (
    IAMConflictError,
    IAMSecrets,
    IAMStore,
    SigningKeyRecord,
)

PUBLISH_AHEAD = timedelta(minutes=15)
RETIRE_AFTER = timedelta(minutes=20)
SIGNING_KEY_SECRET = "iam/signing-keys/{kid}"


def issuer_name(install_id: str) -> str:
    return f"urn:abi:engine:{install_id}"


class TokenIssuer:
    def __init__(
        self,
        store: IAMStore,
        secrets: IAMSecrets,
        *,
        access_ttl_seconds: int = MAX_TOKEN_SECONDS,
        rotation_days: int = 30,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        if not 0 < access_ttl_seconds <= MAX_TOKEN_SECONDS:
            raise ValueError(f"access tokens live at most {MAX_TOKEN_SECONDS} seconds")
        self._store = store
        self._secrets = secrets
        self._ttl = access_ttl_seconds
        self._rotation = timedelta(days=rotation_days)
        self._clock = clock
        self._lock = threading.Lock()
        self._private: dict[str, SigningKey] = {}
        self.issuer = issuer_name(store.install_id())

    # -- issuing ------------------------------------------------------------------

    def issue(
        self,
        subject: str,
        *,
        kind: str,
        audience: str,
        name: str | None = None,
        ttl_seconds: int | None = None,
    ) -> IssuedToken:
        """A signed token for ``subject``; callers decide who may have one."""
        ttl = min(ttl_seconds or self._ttl, self._ttl)
        now = self._clock()
        key = self._current_key(now)
        issued_at = epoch(now)
        claims = TokenClaims(
            issuer=self.issuer,
            subject=subject,
            audience=audience,
            kind=kind,
            token_id=new_token_id(),
            issued_at=issued_at,
            expires_at=issued_at + ttl,
            name=name,
        )
        return IssuedToken(
            sign_token(key, claims), float(claims.expires_at), subject, name or ""
        )

    def jwks(self) -> dict[str, Any]:
        """The published keys (RFC 7517) and the issuer they sign for."""
        now = self._clock()
        self._current_key(now)  # rotates when due, so the next key is published
        keys = [
            record.public_jwk
            for record in self._store.list_signing_keys()
            if record.created_at <= now
            and (record.retires_at is None or now < record.retires_at)
        ]
        return {"issuer": self.issuer, "keys": keys}

    # -- keys -----------------------------------------------------------------------

    def _current_key(self, now: datetime) -> SigningKey:
        with self._lock:
            records = self._store.list_signing_keys()
            usable = [
                r
                for r in records
                if r.activates_at <= now
                and (r.retires_at is None or now < r.retires_at)
                and self._load(r.kid) is not None
            ]
            current = max(usable, key=lambda r: r.activates_at, default=None)
            if current is None:
                # First boot, or the private halves are gone: sign at once.
                current = self._create(now, now)
            self._retire_older(records, current)
            due = current.activates_at + self._rotation - PUBLISH_AHEAD
            pending = [r for r in records if r.activates_at > now]
            if now >= due and not pending:
                self._create(now, max(now + PUBLISH_AHEAD, due + PUBLISH_AHEAD))
            key = self._load(current.kid)
            assert key is not None
            return key

    def _retire_older(
        self, records: list[SigningKeyRecord], current: SigningKeyRecord
    ) -> None:
        for record in records:
            if record.activates_at < current.activates_at and record.retires_at is None:
                self._store.retire_signing_key(
                    record.kid, current.activates_at + RETIRE_AFTER
                )

    def _create(self, now: datetime, activates_at: datetime) -> SigningKeyRecord:
        key = SigningKey.generate(now)
        self._secrets.put(
            SIGNING_KEY_SECRET.format(kid=key.kid),
            base64.urlsafe_b64encode(key.private_pem().encode()).decode(),
        )
        record = SigningKeyRecord(key.kid, key.public_jwk(), now, activates_at)
        try:
            self._store.add_signing_key(record)
        except IAMConflictError:  # 32 random bits collided on the same day
            return self._create(now, activates_at)
        self._private[key.kid] = key
        logger.info(f"IAM signing key {key.kid} published, signs from {activates_at}")
        return record

    def _load(self, kid: str) -> SigningKey | None:
        key = self._private.get(kid)
        if key is not None:
            return key
        encoded = self._secrets.get(SIGNING_KEY_SECRET.format(kid=kid))
        if not encoded:
            return None
        try:
            key = SigningKey.from_pem(kid, base64.urlsafe_b64decode(encoded).decode())
        except (ValueError, TypeError) as exc:
            logger.warning(f"IAM signing key {kid} is unreadable: {exc}")
            return None
        self._private[kid] = key
        return key
