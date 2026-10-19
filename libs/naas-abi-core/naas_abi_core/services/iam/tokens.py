"""The engine's token issuer: ES256 signing keys, their rotation and the JWKS.

RFC §9.1:

* a key is named ``<yyyymmdd>-<8 hex>``; its public half and its schedule are
  in the store (``SigningKeyRecord``), its private half in ``IAMSecrets`` at
  ``iam/signing-keys/<kid>``, sealed to ``engine``;
* keys rotate every ``rotation_days``: the next key is published at least
  ``PUBLISH_AHEAD`` before it signs, and a key stays published for
  ``RETIRE_AFTER`` after the next one took over (a token lives ten minutes);
* a retired key's public half stays in the JWKS ``VERIFY_RETIRED_FOR`` more,
  marked ``abi_retired_at``, for the calls stored while it signed: a job
  trigger waits in its stream up to seven days and is checked as of its stored
  time. Verifiers accept it for that and for nothing else (a token is never
  accepted live, or as of a later time, from a retired key), and its private
  half is deleted at retirement;
* the JWKS names the issuer, ``urn:abi:engine:<install id>``, next to the keys.

Rotation is checked whenever a token is issued or the JWKS read: no timer.
"""

from __future__ import annotations

import base64
import threading
from collections.abc import Callable, Mapping, Sequence
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
# The longest a stored call waits (a job trigger: 168 hours), and an hour more.
VERIFY_RETIRED_FOR = timedelta(hours=169)
SIGNING_KEY_SECRET = "iam/signing-keys/{kid}"
# The JWK member naming when a retired key stopped signing and verifying live
# tokens (epoch seconds). nats_auth.RETIRED_AT_MEMBER reads it.
RETIRED_AT = "abi_retired_at"


def issuer_name(install_id: str) -> str:
    return f"urn:abi:engine:{install_id}"


# What a token's ``abi_scope`` may hold: a few Allow statements, so a token
# stays small and cheap to evaluate.
MAX_SCOPE_STATEMENTS = 32
MAX_SCOPE_PATTERNS = 64
MAX_PATTERN_LENGTH = 512


def normalize_scope(
    scope: Sequence[Mapping[str, Any]] | None,
) -> tuple[dict[str, Any], ...] | None:
    """``scope`` as the claim stores it, or ``ValueError`` naming what is wrong.

    A list of Allow statements, each with ``actions`` and ``resources`` as
    non-empty lists of strings (the evaluator reads nothing else, so a stricter
    shape here is only a friendlier error). ``None`` is no narrowing; ``()``
    allows nothing.
    """
    if scope is None:
        return None
    if isinstance(scope, (str, bytes, Mapping)) or not isinstance(scope, Sequence):
        raise ValueError("scope must be a list of Allow statements")  # noqa: TRY004 - payload validation
    if len(scope) > MAX_SCOPE_STATEMENTS:
        raise ValueError(f"scope holds at most {MAX_SCOPE_STATEMENTS} statements")
    statements: list[dict[str, Any]] = []
    for index, statement in enumerate(scope):
        where = f"scope statement {index}"
        if not isinstance(statement, Mapping):
            raise ValueError(f"{where} must be an object")  # noqa: TRY004 - payload validation
        if statement.get("effect") != "Allow":
            raise ValueError(f"{where}: effect must be Allow (a scope only narrows)")
        normalized: dict[str, Any] = {"effect": "Allow"}
        for field in ("actions", "resources"):
            patterns = statement.get(field)
            if (
                not isinstance(patterns, (list, tuple))
                or not patterns
                or len(patterns) > MAX_SCOPE_PATTERNS
                or not all(
                    isinstance(p, str) and 0 < len(p) <= MAX_PATTERN_LENGTH
                    for p in patterns
                )
            ):
                raise ValueError(
                    f"{where}: {field} must be a list of 1 to "
                    f"{MAX_SCOPE_PATTERNS} patterns"
                )
            normalized[field] = list(patterns)
        statements.append(normalized)
    return tuple(statements)


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
        self._purged: set[str] = set()
        self.issuer = issuer_name(store.install_id())

    # -- issuing ------------------------------------------------------------------

    def now(self) -> datetime:
        """The issuer's clock: what ``iat`` and every cap on a token are read from."""
        return self._clock()

    def issue(
        self,
        subject: str,
        *,
        kind: str,
        audience: str,
        name: str | None = None,
        ttl_seconds: int | None = None,
        not_after: int | None = None,
        actor: str | None = None,
        actor_name: str | None = None,
        groups: Sequence[str] = (),
        scope: Sequence[Mapping[str, Any]] | None = None,
        session: str | None = None,
        since: int | None = None,
        resource: str | None = None,
    ) -> IssuedToken:
        """A signed token for ``subject``; callers decide who may have one.

        ``not_after``: the token never outlives this (epoch seconds), whatever
        its ttl: the end of a delegation that may only be renewed so long.
        """
        ttl = min(ttl_seconds or self._ttl, self._ttl)
        now = self._clock()
        key = self._current_key(now)
        issued_at = epoch(now)
        expires_at = issued_at + ttl
        if not_after is not None:
            expires_at = min(expires_at, not_after)
        claims = TokenClaims(
            issuer=self.issuer,
            subject=subject,
            audience=audience,
            kind=kind,
            token_id=new_token_id(),
            issued_at=issued_at,
            expires_at=expires_at,
            name=name,
            actor=actor,
            actor_name=actor_name,
            groups=tuple(groups),
            scope=tuple(scope) if scope is not None else None,
            session=session,
            since=issued_at if since is None else since,
            resource=resource,
        )
        return IssuedToken(
            sign_token(key, claims),
            float(claims.expires_at),
            subject,
            name or "",
            audience,
        )

    def jwks(self) -> dict[str, Any]:
        """The published keys (RFC 7517) and the issuer they sign for."""
        now = self._clock()
        self._current_key(now)  # rotates when due, so the next key is published
        keys: list[dict[str, Any]] = []
        for record in self._store.list_signing_keys():
            if record.created_at > now:
                continue
            jwk = dict(record.public_jwk)
            if record.retires_at is not None:
                if now >= record.retires_at + VERIFY_RETIRED_FOR:
                    continue
                jwk[RETIRED_AT] = int(record.retires_at.timestamp())
            keys.append(jwk)
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
            self._purge_retired(records, now)
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

    def _purge_retired(self, records: list[SigningKeyRecord], now: datetime) -> None:
        """Delete the private half of every key that stopped verifying live
        tokens: nothing signs with it again, and a copy leaked later forges
        nothing."""
        for record in records:
            if (
                record.retires_at is None
                or now < record.retires_at
                or record.kid in self._purged
            ):
                continue
            self._purged.add(record.kid)
            self._private.pop(record.kid, None)
            try:
                self._secrets.delete(SIGNING_KEY_SECRET.format(kid=record.kid))
            except Exception as exc:  # noqa: BLE001 - best effort, tried next process
                logger.warning(f"IAM signing key {record.kid} was not deleted: {exc}")

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
