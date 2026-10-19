"""Engine-issued ES256 tokens, their JWKS verification and token sources.

See docs/specs/rfcs/20261013_identity-and-authorization.md, §9.1 and §9.2.

* Only the engine signs, with an ES256 key named by its ``kid``; IAM holds the
  keys (``services/iam/tokens.py``) and publishes their public halves as a JWKS
  (``abi.iam.v1.jwks``). Nothing else holds a signing key.
* A verifier needs only the JWKS: :class:`JWKSVerifier` caches it for five
  minutes and refetches on an unknown ``kid`` at most every 30 seconds.
* No token lives longer than ten minutes: the issuer refuses to sign one and
  verifiers refuse to accept one (``exp - iat > 600``), with 30 seconds of
  clock skew.
* A process that calls with tokens holds a :class:`TokenSource`: an in-process
  issuer (the serving engine), or a service key exchanged at
  ``abi.iam.v1.token`` (modules, scripts, client-role engines). Either renews
  at half the token's life.
"""

from __future__ import annotations

import base64
import json
import math
import os
import re
import secrets
import threading
import time
from abc import ABC, abstractmethod
from collections import OrderedDict
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec

ALGORITHM = "ES256"
MAX_TOKEN_SECONDS = 600
CLOCK_SKEW_SECONDS = 30
NATS_AUDIENCE = "abi:nats"
# A Nexus session: a user after an identity-provider login. The only audience
# the Nexus API and WebSocket accept.
SESSION_AUDIENCE = "abi:session"
# Narrow credentials derived by token exchange (RFC 8693, §9.4), each with its
# own audience and none of them a session:
# * agent: a module acting for a user (``act`` is the module's account); also
#   what a first-party service sends the kernel for the user it serves.
# * app / preview: opening a remote app or an app-html link, a project preview.
# * coding: a coding environment's agent, for the user who owns it.
# * api-key: a personal API key.
AGENT_AUDIENCE = "abi:delegated:agent"
APP_AUDIENCE = "abi:delegated:app"
PREVIEW_AUDIENCE = "abi:delegated:preview"
CODING_AUDIENCE = "abi:delegated:coding"
API_KEY_AUDIENCE = "abi:delegated:api-key"
DELEGATED_AUDIENCES = (
    AGENT_AUDIENCE,
    APP_AUDIENCE,
    PREVIEW_AUDIENCE,
    CODING_AUDIENCE,
    API_KEY_AUDIENCE,
)
# What token exchange may issue; key exchange issues none of these.
EXCHANGE_AUDIENCES = (SESSION_AUDIENCE, *DELEGATED_AUDIENCES)
# What every kernel NATS endpoint accepts: a service's own token, or a module
# acting for a user.
KERNEL_AUDIENCES = (NATS_AUDIENCE, AGENT_AUDIENCE)
# The longest a chain of renewals of one delegation lives (``abi_since``): a
# run outlives its ten-minute token by renewing it, up to this.
MAX_DELEGATION_SECONDS = 8 * 3600
# Delegations a token source keeps (one per user, groups and recipient).
MAX_DELEGATIONS = 2048
# A token addressed to one module host (an agent, a model, an app, a job's
# host), which forwards it to discovery to learn who called. Its audience names
# the host: ``abi:host:<host's subject token>`` (the ``<sa>`` of the subjects it
# serves). Kernel services refuse it (they accept ``abi:nats`` only), and
# discovery accepts it only from the host it names, so a host that keeps one
# can use it nowhere else: not at the kernel, not at another host.
HOST_AUDIENCE_PREFIX = "abi:host:"
_RECIPIENT = re.compile(r"[A-Za-z0-9_-]{1,64}")


def host_audience(recipient: str) -> str:
    """The audience of a token for the host whose subjects carry ``recipient``."""
    if not _RECIPIENT.fullmatch(recipient or ""):
        raise ValueError(f"Not a host recipient: {recipient!r}")
    return HOST_AUDIENCE_PREFIX + recipient


def is_host_audience(audience: str) -> bool:
    return audience.startswith(HOST_AUDIENCE_PREFIX) and bool(
        _RECIPIENT.fullmatch(audience[len(HOST_AUDIENCE_PREFIX) :])
    )


def is_delegated_audience(audience: str) -> bool:
    return audience in DELEGATED_AUDIENCES


def issuable_audience(audience: str) -> bool:
    """The audiences a key or the engine mints tokens for."""
    return audience == NATS_AUDIENCE or is_host_audience(audience)


TOKEN_KINDS = ("user", "service_account")
JWKS_SUBJECT = "abi.iam.v1.jwks"
TOKEN_SUBJECT = "abi.iam.v1.token"


class InvalidServiceTokenError(Exception):
    """A token that failed verification: signature, issuer, audience, lifetime,
    claims. Callers treat every cause alike (refuse the call)."""


# ---------------------------------------------------------------------------
# Claims
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TokenClaims:
    """What an engine token says (RFC §9.2).

    ``name`` (claim ``abi_name``) is a service account's name (``engine``,
    ``module/acme/people``), set by IAM. ``actor`` is ``act.sub`` and
    ``actor_name`` ``act.name``: the actor's account name, set by IAM from its
    record, so a service that asks who acts (``api``, a module) is told by the
    token.
    ``since`` (``abi_since``): when the delegation began, kept across renewals
    so they stop after ``MAX_DELEGATION_SECONDS``. ``resource`` (``abi_res``):
    the target the exchange was for, for audit and for the routes that bind a
    token to one thing.
    """

    issuer: str
    subject: str
    audience: str
    kind: str
    token_id: str
    issued_at: int
    expires_at: int
    name: str | None = None
    actor: str | None = None
    groups: tuple[str, ...] = ()
    scope: tuple[Mapping[str, Any], ...] | None = None
    session: str | None = None
    since: int | None = None
    resource: str | None = None
    actor_name: str | None = None

    @property
    def lifetime(self) -> int:
        return self.expires_at - self.issued_at

    def to_payload(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "iss": self.issuer,
            "sub": self.subject,
            "aud": self.audience,
            "kind": self.kind,
            "jti": self.token_id,
            "iat": self.issued_at,
            "nbf": self.issued_at,
            "exp": self.expires_at,
        }
        if self.name is not None:
            payload["abi_name"] = self.name
        if self.actor is not None:
            payload["act"] = {"sub": self.actor}
            if self.actor_name is not None:
                payload["act"]["name"] = self.actor_name
        if self.groups:
            payload["grp"] = list(self.groups)
        if self.scope is not None:
            payload["abi_scope"] = [dict(s) for s in self.scope]
        if self.session is not None:
            payload["sid"] = self.session
        if self.since is not None:
            payload["abi_since"] = self.since
        if self.resource is not None:
            payload["abi_res"] = self.resource
        return payload

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> TokenClaims:
        """Typed claims; ``InvalidServiceTokenError`` for a missing or malformed one."""

        def text(name: str) -> str:
            value = payload.get(name)
            if not isinstance(value, str) or not value:
                raise InvalidServiceTokenError(f"token has no valid {name!r} claim")
            return value

        def optional_text(name: str) -> str | None:
            value = payload.get(name)
            if value is None:
                return None
            if not isinstance(value, str) or not value:
                raise InvalidServiceTokenError(f"token has an invalid {name!r} claim")
            return value

        def integer(name: str) -> int:
            value = payload.get(name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise InvalidServiceTokenError(f"token has no valid {name!r} claim")
            return value

        def optional_integer(name: str) -> int | None:
            if payload.get(name) is None:
                return None
            return integer(name)

        kind = text("kind")
        if kind not in TOKEN_KINDS:
            raise InvalidServiceTokenError(f"token has an unknown kind {kind!r}")
        actor = payload.get("act")
        actor_name = None
        if actor is not None:
            if not isinstance(actor, Mapping) or not isinstance(actor.get("sub"), str):
                raise InvalidServiceTokenError("token has an invalid 'act' claim")
            actor_name = actor.get("name")
            if actor_name is not None and not isinstance(actor_name, str):
                raise InvalidServiceTokenError("token has an invalid 'act' claim")
            actor = actor["sub"]
        groups = payload.get("grp", [])
        if not isinstance(groups, list) or not all(isinstance(g, str) for g in groups):
            raise InvalidServiceTokenError("token has an invalid 'grp' claim")
        scope = payload.get("abi_scope")
        if scope is not None and (
            not isinstance(scope, list)
            or not all(isinstance(s, Mapping) for s in scope)
        ):
            raise InvalidServiceTokenError("token has an invalid 'abi_scope' claim")
        audience = payload.get("aud")
        if isinstance(audience, list) and len(audience) == 1:
            audience = audience[0]
        if not isinstance(audience, str) or not audience:
            raise InvalidServiceTokenError("token must name exactly one audience")
        return cls(
            issuer=text("iss"),
            subject=text("sub"),
            audience=audience,
            kind=kind,
            token_id=text("jti"),
            issued_at=integer("iat"),
            expires_at=integer("exp"),
            name=optional_text("abi_name"),
            actor=actor,
            groups=tuple(groups),
            scope=tuple(scope) if scope is not None else None,
            session=optional_text("sid"),
            since=optional_integer("abi_since"),
            resource=optional_text("abi_res"),
            actor_name=actor_name or None,
        )


def new_token_id() -> str:
    return secrets.token_urlsafe(16)


# ---------------------------------------------------------------------------
# Signing keys
# ---------------------------------------------------------------------------


def _b64url_uint(value: int) -> str:
    raw = value.to_bytes(32, "big")
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


@dataclass(frozen=True)
class SigningKey:
    """A P-256 private key and its ``kid`` (``<yyyymmdd>-<8 hex>``)."""

    kid: str
    private_key: ec.EllipticCurvePrivateKey = field(repr=False)

    @classmethod
    def generate(cls, now: datetime | None = None) -> SigningKey:
        day = (now or datetime.now(UTC)).strftime("%Y%m%d")
        return cls(
            f"{day}-{os.urandom(4).hex()}", ec.generate_private_key(ec.SECP256R1())
        )

    @classmethod
    def from_pem(cls, kid: str, pem: str) -> SigningKey:
        key = serialization.load_pem_private_key(pem.encode(), password=None)
        if not isinstance(key, ec.EllipticCurvePrivateKey) or not isinstance(
            key.curve, ec.SECP256R1
        ):
            raise TypeError(f"Signing key {kid} is not a P-256 key")
        return cls(kid, key)

    def private_pem(self) -> str:
        return self.private_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode()

    def public_jwk(self) -> dict[str, str]:
        numbers = self.private_key.public_key().public_numbers()
        return {
            "kty": "EC",
            "crv": "P-256",
            "x": _b64url_uint(numbers.x),
            "y": _b64url_uint(numbers.y),
            "kid": self.kid,
            "alg": ALGORITHM,
            "use": "sig",
        }


def sign_token(key: SigningKey, claims: TokenClaims) -> str:
    """The signed token; refuses a lifetime above ten minutes."""
    if not 0 < claims.lifetime <= MAX_TOKEN_SECONDS:
        raise ValueError(f"A token lives at most {MAX_TOKEN_SECONDS} seconds")
    return jwt.encode(
        claims.to_payload(),
        key.private_key,
        algorithm=ALGORITHM,
        headers={"kid": key.kid},
    )


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------


# The JWKS member of a retired key: when it stopped signing (epoch seconds).
RETIRED_AT_MEMBER = "abi_retired_at"


class TokenVerifier(ABC):
    """Verifies engine tokens; every NATS primary adapter holds one."""

    @abstractmethod
    def verify(self, token: str, *, at: float | None = None) -> TokenClaims:
        """The claims of a valid token, else ``InvalidServiceTokenError``.

        ``at``: when the token had to be valid (seconds since the epoch), by
        default now: a stored call (a job trigger) is checked as of when it
        was stored."""

    @abstractmethod
    def for_audiences(
        self, audiences: Iterable[str], prefixes: Iterable[str] = ()
    ) -> TokenVerifier:
        """A verifier of the same keys that accepts ``audiences`` (and the
        audiences that start with one of ``prefixes``) only."""


class JWKSVerifier(TokenVerifier):
    """Verifies against the engine's JWKS (RFC §9.1).

    ``fetch`` returns the key set: ``{"issuer": ..., "keys": [...]}``. The
    issuer travels with the keys, so a verifier needs no configuration of its
    own. The set is cached ``cache_seconds``; an unknown ``kid`` refetches it,
    at most once every ``refetch_seconds``.

    When the JWKS cannot be read, the keys already known keep verifying for
    ``stale_seconds`` past their cache, and the next attempt waits
    ``retry_seconds``.

    ``revoked``: asked about every token that otherwise verifies; true refuses
    it. The engine's own verifier knows IAM's revocations (a principal's
    tokens revoked at once, ``IAMService.token_revoked``); one that only has
    the JWKS cannot, and tokens live ten minutes at most. One thread fetches at a time, outside the lock every
    ``verify`` takes: the others keep verifying with the keys they have, or
    wait for that one fetch when they have none.
    """

    def __init__(
        self,
        fetch: Callable[[], Mapping[str, Any]],
        *,
        audiences: Iterable[str] = (NATS_AUDIENCE,),
        audience_prefixes: Iterable[str] = (),
        revoked: Callable[[TokenClaims], bool] | None = None,
        cache_seconds: float = 300.0,
        refetch_seconds: float = 30.0,
        retry_seconds: float = 5.0,
        stale_seconds: float = 900.0,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._fetch = fetch
        self.audiences = frozenset(audiences)
        self.audience_prefixes = tuple(audience_prefixes)
        self._revoked = revoked
        if not self.audiences and not self.audience_prefixes:
            raise ValueError("A verifier accepts at least one audience")
        self._cache_seconds = cache_seconds
        self._refetch_seconds = refetch_seconds
        self._retry_seconds = retry_seconds
        self._stale_seconds = stale_seconds
        self._clock = clock
        self._lock = threading.Lock()
        self._fetching = threading.Lock()
        self._keys: dict[str, tuple[Any, float | None]] = {}
        self._issuer: str | None = None
        self._fetched_at = float("-inf")  # last read
        self._attempted_at = float("-inf")  # last attempt, read or not
        self._failed = False
        self._error = ""

    def for_audiences(
        self, audiences: Iterable[str], prefixes: Iterable[str] = ()
    ) -> JWKSVerifier:
        return JWKSVerifier(
            self._fetch,
            audiences=audiences,
            audience_prefixes=prefixes,
            revoked=self._revoked,
            cache_seconds=self._cache_seconds,
            refetch_seconds=self._refetch_seconds,
            retry_seconds=self._retry_seconds,
            stale_seconds=self._stale_seconds,
            clock=self._clock,
        )

    def verify(self, token: str, *, at: float | None = None) -> TokenClaims:
        if not token or not isinstance(token, str):
            raise InvalidServiceTokenError("missing token")
        if at is not None and not math.isfinite(at):
            raise InvalidServiceTokenError("invalid validity time")
        try:
            header = jwt.get_unverified_header(token)
        except jwt.InvalidTokenError as exc:
            raise InvalidServiceTokenError(str(exc)) from exc
        if header.get("alg") != ALGORITHM:
            raise InvalidServiceTokenError(f"token is not {ALGORITHM}")
        kid = header.get("kid")
        if not isinstance(kid, str) or not kid:
            raise InvalidServiceTokenError("token names no key")
        key, issuer, retired_at = self._key(kid)
        try:
            payload = jwt.decode(
                token,
                key,
                algorithms=[ALGORITHM],
                issuer=issuer,
                leeway=CLOCK_SKEW_SECONDS,
                options={
                    "require": ["iss", "sub", "aud", "exp", "iat", "jti"],
                    "verify_aud": False,
                    # As of ``at``: checked below instead of against now.
                    "verify_exp": at is None,
                    "verify_iat": at is None,
                    "verify_nbf": at is None,
                },
            )
        except jwt.InvalidTokenError as exc:
            raise InvalidServiceTokenError(str(exc)) from exc
        claims = TokenClaims.from_payload(payload)
        if retired_at is not None:
            # A retired key vouches for what it signed while it signed: a call
            # stored back then (``at``), never a token presented now, or one
            # dated after its retirement.
            when = self._clock() if at is None else at
            if when > retired_at + CLOCK_SKEW_SECONDS or (
                claims.issued_at > retired_at + CLOCK_SKEW_SECONDS
            ):
                raise InvalidServiceTokenError(f"signing key {kid!r} is retired")
        if at is not None and not (
            claims.issued_at - CLOCK_SKEW_SECONDS
            <= at
            <= claims.expires_at + CLOCK_SKEW_SECONDS
        ):
            raise InvalidServiceTokenError(
                "token was not valid when the call was stored"
            )
        if claims.audience not in self.audiences and not any(
            claims.audience.startswith(prefix) for prefix in self.audience_prefixes
        ):
            raise InvalidServiceTokenError(
                f"token audience {claims.audience!r} is not accepted here"
            )
        # PyJWT checked exp, nbf and iat against the wall clock, with the skew.
        if claims.lifetime > MAX_TOKEN_SECONDS or claims.lifetime <= 0:
            raise InvalidServiceTokenError("token lifetime exceeds ten minutes")
        if self._revoked is not None and self._revoked(claims):
            raise InvalidServiceTokenError("token was revoked")
        return claims

    def _key(self, kid: str) -> tuple[Any, str, float | None]:
        if self._should_fetch(kid):
            # One fetch at a time. Without keys to go on, wait for it.
            if self._fetching.acquire(blocking=not self._usable()):
                try:
                    if self._should_fetch(kid):
                        self._load()
                finally:
                    self._fetching.release()
        with self._lock:
            usable = self._usable_locked()
            known = self._keys.get(kid) if usable else None
            issuer, error = self._issuer, self._error
        key, retired_at = known if known is not None else (None, None)
        if key is None or issuer is None:
            if not usable and error:
                raise InvalidServiceTokenError(f"cannot read the JWKS: {error}")
            raise InvalidServiceTokenError(f"unknown signing key {kid!r}")
        return key, issuer, retired_at

    def _should_fetch(self, kid: str) -> bool:
        with self._lock:
            now = self._clock()
            since_attempt = now - self._attempted_at
            if self._failed and since_attempt < self._retry_seconds:
                return False  # backing off
            if now - self._fetched_at >= self._cache_seconds:
                return True
            return kid not in self._keys and since_attempt >= self._refetch_seconds

    def _usable(self) -> bool:
        with self._lock:
            return self._usable_locked()

    def _usable_locked(self) -> bool:
        """Keys to verify with: fresh, or stale for at most ``stale_seconds``."""
        age = self._clock() - self._fetched_at
        return bool(self._keys) and age < self._cache_seconds + self._stale_seconds

    def _load(self) -> None:
        """Fetch the JWKS outside ``_lock``; never raises."""
        started = self._clock()
        try:
            keys, issuer = self._read(self._fetch())
        except Exception as exc:  # noqa: BLE001 - the engine may be restarting
            with self._lock:
                self._attempted_at, self._failed = started, True
                self._error = str(exc) or type(exc).__name__
            return
        with self._lock:
            self._keys, self._issuer = keys, issuer
            self._fetched_at = self._attempted_at = started
            self._failed, self._error = False, ""

    @staticmethod
    def _read(
        jwks: Mapping[str, Any],
    ) -> tuple[dict[str, tuple[Any, float | None]], str]:
        issuer = jwks.get("issuer")
        if not isinstance(issuer, str) or not issuer:
            raise InvalidServiceTokenError("the JWKS names no issuer")
        keys: dict[str, tuple[Any, float | None]] = {}
        for jwk in jwks.get("keys", []):
            if jwk.get("kty") != "EC" or jwk.get("alg", ALGORITHM) != ALGORITHM:
                continue
            try:
                retired = jwk.get(RETIRED_AT_MEMBER)
                keys[jwk["kid"]] = (
                    jwt.PyJWK.from_dict(dict(jwk), ALGORITHM).key,
                    float(retired) if retired is not None else None,
                )
            except (TypeError, ValueError):
                continue
            except (KeyError, jwt.InvalidKeyError, jwt.PyJWKError):
                continue
        return keys, issuer


def jwks_json(jwks: Mapping[str, Any]) -> str:
    return json.dumps(jwks, sort_keys=True, separators=(",", ":"))


# ---------------------------------------------------------------------------
# Token sources: what a calling process holds instead of a secret
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IssuedToken:
    """An access token and when it expires (epoch seconds)."""

    token: str
    expires_at: float
    principal_id: str = ""
    name: str = ""
    audience: str = ""


class TokenSource(ABC):
    """The credential a NATS client presents. ``identity`` names it in
    connection names."""

    identity: str

    @abstractmethod
    def token(self) -> str:
        """A token valid for at least a few more minutes."""

    def token_for(
        self,
        user: Any,
        recipient: str | None = None,
        scope: Sequence[Mapping[str, Any]] | None = None,
    ) -> str:
        """The token of a call made for ``user`` (a ``Principal``): a delegation
        that carries the user, for a source allowed to hold them (``api``,
        ``engine``). Any other source calls as itself: its own token.

        ``recipient``: the ``<sa>`` of the module host the call is for (a
        delegation names the module that acts). ``scope``: the narrowing of the
        credential the call is made under (an API key's), which the delegation
        keeps: a call never reaches further over NATS than it does in process."""
        return self.token()


class RenewingTokenSource(TokenSource):
    """Fetches an :class:`IssuedToken` and fetches a new one at half its life.

    ``fetch`` is an in-process issuer (the serving engine) or a service-key
    exchange over NATS. A failed renewal keeps the current token while it is
    still valid and raises once it is not.
    """

    def __init__(
        self,
        identity: str,
        fetch: Callable[[], IssuedToken],
        *,
        delegate: Callable[[Any, str | None, Any], IssuedToken] | None = None,
        clock: Callable[[], float] = time.time,
    ) -> None:
        """``delegate(user, recipient, scope)``: a token carrying ``user`` (token
        exchange). Without one, ``token_for`` is the source's own token."""
        if not identity:
            raise ValueError("A token source names its identity")
        self.identity = identity
        self._fetch = fetch
        self._delegate = delegate
        self._clock = clock
        self._lock = threading.Lock()
        self._current: IssuedToken | None = None
        self._renew_at = float("-inf")
        # (user id, groups, recipient) -> (token, renew at). Bounded: a long
        # running API serves many users.
        self._delegations: OrderedDict[
            tuple[str, tuple[str, ...], str | None, str | None],
            tuple[IssuedToken, float],
        ] = OrderedDict()

    def token(self) -> str:
        with self._lock:
            now = self._clock()
            if self._current is None or now >= self._renew_at:
                try:
                    issued = self._fetch()
                except Exception:
                    if self._current is not None and now < self._current.expires_at - 5:
                        return self._current.token
                    raise
                self._current = issued
                self._renew_at = now + max(1.0, (issued.expires_at - now) / 2)
            return self._current.token

    def token_for(
        self,
        user: Any,
        recipient: str | None = None,
        scope: Sequence[Mapping[str, Any]] | None = None,
    ) -> str:
        if user is None or self._delegate is None:
            return self.token()
        key = (
            user.id,
            tuple(sorted(user.groups)),
            recipient,
            json.dumps(list(scope), sort_keys=True) if scope is not None else None,
        )
        with self._lock:
            now = self._clock()
            held = self._delegations.get(key)
            if held is not None and now < held[1]:
                self._delegations.move_to_end(key)
                return held[0].token
            try:
                issued = self._delegate(user, recipient, scope)
            except Exception:
                # A delegation that cannot be renewed keeps the valid one; one
                # that cannot be made is an error, never the source's own token
                # (which would drop the user and widen the call).
                if held is not None and now < held[0].expires_at - 5:
                    return held[0].token
                raise
            self._delegations[key] = (
                issued,
                now + max(1.0, (issued.expires_at - now) / 2),
            )
            self._delegations.move_to_end(key)
            while len(self._delegations) > MAX_DELEGATIONS:
                self._delegations.popitem(last=False)
            return issued.token

    def invalidate(self) -> None:
        """Fetch a new token on next use (after the server refused this one)."""
        with self._lock:
            self._renew_at = float("-inf")
            self._delegations.clear()


class StaticTokenSource(TokenSource):
    """One fixed token, for tests and one-shot scripts."""

    def __init__(self, token: str, identity: str = "static") -> None:
        self.identity = identity
        self._token = token

    def token(self) -> str:
        return self._token


# ---------------------------------------------------------------------------
# Service keys (RFC §8.1): abi_sk_<key id>_<secret>
# ---------------------------------------------------------------------------

SERVICE_KEY_PREFIX = "abi_sk_"
PERSONAL_KEY_PREFIX = "abi_pk_"
# The link of an app or a preview: a key of a user's, valid for hours.
GRANT_KEY_PREFIX = "abi_gk_"


def parse_key(key: str) -> tuple[str, str, str]:
    """``(prefix, key id, secret)`` of an ``abi_sk_``/``abi_pk_``/``abi_gk_`` key;
    ``ValueError`` when it is not one."""
    for prefix in (SERVICE_KEY_PREFIX, PERSONAL_KEY_PREFIX, GRANT_KEY_PREFIX):
        if key.startswith(prefix):
            key_id, sep, secret = key[len(prefix) :].partition("_")
            if (
                sep
                and len(key_id) == 16
                and key_id.isalnum()
                and key_id == key_id.lower()
                and secret
            ):
                return prefix, key_id, secret
    raise ValueError("not an ABI key (abi_<sk|pk|gk>_<key id>_<secret>)")


def epoch(value: datetime) -> int:
    return int(value.timestamp())
