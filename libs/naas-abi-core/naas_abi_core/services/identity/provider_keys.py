"""A provider's discovery document and signing keys, cached (RFC §9.1, §12.1).

* The discovery document is read from ``<issuer>/.well-known/openid-configuration``
  and must name exactly the configured issuer (OIDC Discovery §4.3).
* The JWKS is cached for its ``Cache-Control: max-age`` (5 minutes when it
  states none, an hour at most). A token signed with a key the cache does not
  hold refetches it, at most once every ``refetch_seconds``: that is how key
  rotation is followed.
* When the provider cannot be read, the keys already known keep verifying for
  ``stale_seconds`` past their cache, and the next attempt waits
  ``retry_seconds``.

One thread fetches at a time; the others keep verifying with the keys they
have, or wait for that fetch when they have none.
"""

from __future__ import annotations

import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlsplit

import jwt

from naas_abi_core.services.identity.IdentityPorts import (
    ALLOWED_ALGORITHMS,
    IdentityProvider,
    OIDCHttpPort,
    ProviderMetadata,
    ProviderUnavailableError,
    TokenRejectedError,
)

DISCOVERY_PATH = "/.well-known/openid-configuration"
_MAX_CACHE_SECONDS = 3600.0


def discovery_url(issuer: str) -> str:
    return issuer.rstrip("/") + DISCOVERY_PATH


def is_local_host(host: str | None) -> bool:
    return host in {"localhost", "127.0.0.1", "::1"} or bool(
        host and host.endswith(".localhost")
    )


def check_endpoint_url(url: str, *, what: str) -> str:
    """``https``, or ``http`` on a loopback host only (as the issuer itself)."""
    parts = urlsplit(url)
    if parts.scheme == "https" and parts.netloc:
        return url
    if parts.scheme == "http" and is_local_host(parts.hostname):
        return url
    raise ValueError(f"{what} must be https (http on localhost only): {url!r}")


def parse_metadata(
    provider: IdentityProvider, document: Mapping[str, Any]
) -> ProviderMetadata:
    """The discovery document, checked against the configured issuer."""
    issuer = document.get("issuer")
    if issuer != provider.issuer:
        raise ProviderUnavailableError(
            f"Provider {provider.name}: the discovery document names issuer "
            f"{issuer!r}, not the configured {provider.issuer!r}"
        )

    def endpoint(key: str, required: bool) -> str | None:
        value = document.get(key)
        if value is None and not required:
            return None
        if not isinstance(value, str) or not value:
            raise ProviderUnavailableError(
                f"Provider {provider.name}: the discovery document has no {key}"
            )
        try:
            return check_endpoint_url(value, what=f"{provider.name} {key}")
        except ValueError as exc:
            raise ProviderUnavailableError(str(exc)) from exc

    def strings(key: str) -> tuple[str, ...]:
        value = document.get(key)
        if not isinstance(value, list):
            return ()
        return tuple(v for v in value if isinstance(v, str))

    algorithms = tuple(
        a
        for a in strings("id_token_signing_alg_values_supported")
        if a in ALLOWED_ALGORITHMS
    )
    return ProviderMetadata(
        issuer=provider.issuer,
        authorization_endpoint=endpoint("authorization_endpoint", True) or "",
        token_endpoint=endpoint("token_endpoint", True) or "",
        jwks_uri=endpoint("jwks_uri", True) or "",
        userinfo_endpoint=endpoint("userinfo_endpoint", False),
        revocation_endpoint=endpoint("revocation_endpoint", False),
        end_session_endpoint=endpoint("end_session_endpoint", False),
        signing_algorithms=algorithms or ("RS256",),
        code_challenge_methods=strings("code_challenge_methods_supported"),
    )


class _Cached:
    """One cached document: when it was read, for how long, and the last error."""

    def __init__(self) -> None:
        self.fetched_at = float("-inf")
        self.attempted_at = float("-inf")
        # None until the provider states one: 0 is a real answer (no-store).
        self.max_age: float | None = None
        self.failed = False
        self.error = ""


class ProviderKeys:
    """Discovery and JWKS for one provider."""

    def __init__(
        self,
        provider: IdentityProvider,
        http: OIDCHttpPort,
        *,
        jwks_cache_seconds: float = 300.0,
        discovery_cache_seconds: float = 3600.0,
        refetch_seconds: float = 30.0,
        retry_seconds: float = 5.0,
        stale_seconds: float = 900.0,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.provider = provider
        self._http = http
        self._jwks_cache_seconds = jwks_cache_seconds
        self._discovery_cache_seconds = discovery_cache_seconds
        self._refetch_seconds = refetch_seconds
        self._retry_seconds = retry_seconds
        self._stale_seconds = stale_seconds
        self._clock = clock
        self._lock = threading.Lock()
        # One fetch of each document at a time. Reading the JWKS reads discovery
        # first, so each has its own lock.
        self._fetching_metadata = threading.Lock()
        self._fetching_keys = threading.Lock()
        self._metadata: ProviderMetadata | None = None
        self._metadata_state = _Cached()
        self._keys: dict[str, SigningKey] = {}
        self._keys_state = _Cached()

    # -- discovery --------------------------------------------------------------

    def metadata(self) -> ProviderMetadata:
        if self._needs(self._metadata_state, self._discovery_cache_seconds, False):
            with self._fetching_metadata:
                if self._needs(
                    self._metadata_state, self._discovery_cache_seconds, False
                ):
                    self._load_metadata()
        with self._lock:
            metadata, state = self._metadata, self._metadata_state
            usable = metadata is not None and self._usable(
                state, self._discovery_cache_seconds
            )
        if not usable or metadata is None:
            raise ProviderUnavailableError(
                f"Provider {self.provider.name}: cannot read its discovery document"
                + (f": {state.error}" if state.error else "")
            )
        return metadata

    def _load_metadata(self) -> None:
        started = self._clock()
        try:
            answer = self._http.get_json(discovery_url(self.provider.issuer))
            metadata = parse_metadata(self.provider, answer.body)
        except Exception as exc:  # noqa: BLE001 - recorded, raised by metadata()
            self._failed(self._metadata_state, started, exc)
            return
        with self._lock:
            self._metadata = metadata
            self._succeeded(self._metadata_state, started, answer.max_age)

    # -- keys -------------------------------------------------------------------

    def key(self, kid: str | None, algorithm: str) -> SigningKey:
        """The key that signed a token: by ``kid``, else the only key of its type."""
        if self._needs_keys(kid):
            # One fetch at a time. Without keys to go on, wait for it.
            if self._fetching_keys.acquire(blocking=not self._has_usable_keys()):
                try:
                    if self._needs_keys(kid):
                        self._load_keys()
                finally:
                    self._fetching_keys.release()
        with self._lock:
            usable = self._usable(self._keys_state, self._jwks_cache_seconds)
            keys = dict(self._keys) if usable else {}
            error = self._keys_state.error
        if not keys:
            raise ProviderUnavailableError(
                f"Provider {self.provider.name}: cannot read its JWKS"
                + (f": {error}" if error else "")
            )
        if kid is not None:
            found = keys.get(kid)
        else:
            candidates = [k for k in keys.values() if k.fits(algorithm)]
            found = candidates[0] if len(candidates) == 1 else None
        if found is None:
            raise TokenRejectedError(
                "unknown_key",
                f"Provider {self.provider.name} publishes no signing key {kid!r}",
            )
        if not found.fits(algorithm):
            raise TokenRejectedError(
                "algorithm", f"Key {found.kid!r} does not sign with {algorithm}"
            )
        return found

    def prefetch(self) -> None:
        """Read the discovery document and the JWKS now; raise when either fails."""
        self.metadata()
        if self._needs(self._keys_state, self._jwks_cache_seconds, True):
            with self._fetching_keys:
                self._load_keys()
        if not self._has_usable_keys():
            raise ProviderUnavailableError(
                f"Provider {self.provider.name}: cannot read its JWKS: "
                f"{self._keys_state.error or 'no usable key'}"
            )

    def known_key_ids(self) -> tuple[str, ...]:
        with self._lock:
            return tuple(self._keys)

    def _needs_keys(self, kid: str | None) -> bool:
        if self._needs(self._keys_state, self._jwks_cache_seconds, True):
            return True
        with self._lock:
            unknown = kid is not None and kid not in self._keys
            since = self._clock() - self._keys_state.attempted_at
            return unknown and since >= self._refetch_seconds

    def _has_usable_keys(self) -> bool:
        with self._lock:
            return bool(self._keys) and self._usable(
                self._keys_state, self._jwks_cache_seconds
            )

    def _load_keys(self) -> None:
        started = self._clock()
        try:
            uri = self.metadata().jwks_uri
            answer = self._http.get_json(uri)
            keys = _parse_jwks(answer.body)
            if not keys:
                raise ProviderUnavailableError("the JWKS holds no usable signing key")
        except Exception as exc:  # noqa: BLE001 - recorded, raised by key()
            self._failed(self._keys_state, started, exc)
            return
        with self._lock:
            self._keys = keys
            self._succeeded(self._keys_state, started, answer.max_age)

    # -- cache bookkeeping ------------------------------------------------------

    def _needs(self, state: _Cached, default_age: float, keys: bool) -> bool:
        with self._lock:
            now = self._clock()
            if state.failed and now - state.attempted_at < self._retry_seconds:
                return False  # backing off
            return now - state.fetched_at >= _age(state, default_age)

    def _usable(self, state: _Cached, default_age: float) -> bool:
        age = self._clock() - state.fetched_at
        return age < _age(state, default_age) + self._stale_seconds

    def _succeeded(self, state: _Cached, started: float, max_age: float | None) -> None:
        state.fetched_at = state.attempted_at = started
        state.max_age = (
            min(max(max_age, 0.0), _MAX_CACHE_SECONDS) if max_age is not None else None
        )
        state.failed, state.error = False, ""

    def _failed(self, state: _Cached, started: float, exc: Exception) -> None:
        with self._lock:
            state.attempted_at, state.failed = started, True
            state.error = str(exc) or type(exc).__name__


def _age(state: _Cached, default_age: float) -> float:
    return default_age if state.max_age is None else state.max_age


@dataclass(frozen=True)
class SigningKey:
    """A published key, and the algorithm it declares (``alg``), if any."""

    kid: str
    jwk: jwt.PyJWK
    algorithm: str | None

    @property
    def key(self) -> Any:
        return self.jwk.key

    def fits(self, algorithm: str) -> bool:
        """Whether a token signed with ``algorithm`` may use this key."""
        if self.algorithm is not None and self.algorithm != algorithm:
            return False
        return self.jwk.key_type == _KEY_TYPES.get(algorithm[:2])


def _parse_jwks(document: Mapping[str, Any]) -> dict[str, SigningKey]:
    keys: dict[str, SigningKey] = {}
    for index, jwk in enumerate(document.get("keys") or []):
        if not isinstance(jwk, Mapping):
            continue
        if jwk.get("use", "sig") != "sig":
            continue
        algorithm = jwk.get("alg")
        if algorithm is not None and algorithm not in ALLOWED_ALGORITHMS:
            continue
        try:
            parsed = jwt.PyJWK.from_dict(dict(jwk), algorithm)
        except (jwt.InvalidKeyError, jwt.PyJWKError, KeyError, ValueError, TypeError):
            continue
        kid = str(jwk.get("kid") or f"#{index}")
        keys[kid] = SigningKey(kid, parsed, algorithm)
    return keys


_KEY_TYPES = {"RS": "RSA", "PS": "RSA", "ES": "EC", "Ed": "OKP"}
