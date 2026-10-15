"""ID token verification against the configured providers (RFC §9.4, §12.1).

A token is accepted only when:

* its ``iss`` is exactly a configured provider's issuer;
* its signature checks against a key of that provider's JWKS, with an
  asymmetric algorithm (never ``none``, never HMAC) the key allows;
* its ``aud`` holds the provider's ``client_id``, and its ``azp``, when present
  or when there are several audiences, is that ``client_id`` (OIDC Core §3.1.3.7);
* ``exp`` is in the future and ``nbf`` and ``iat`` are not, within the clock skew;
* its ``nonce`` is the expected one, when the caller expects one.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping, Sequence
from typing import Any

import jwt

from naas_abi_core.services.identity.IdentityPorts import (
    ALLOWED_ALGORITHMS,
    IdentityProvider,
    TokenRejectedError,
    VerifiedToken,
    claim_values,
)
from naas_abi_core.services.identity.provider_keys import ProviderKeys

CLOCK_SKEW_SECONDS = 30


class TokenVerifier:
    """Verifies ID tokens for a set of providers, each with its own keys."""

    def __init__(
        self,
        keys: Sequence[ProviderKeys],
        *,
        clock_skew_seconds: int = CLOCK_SKEW_SECONDS,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._by_issuer = {k.provider.issuer: k for k in keys}
        self._skew = clock_skew_seconds
        self._clock = clock

    def provider_keys(self, issuer: str) -> ProviderKeys | None:
        return self._by_issuer.get(issuer)

    def verify(
        self,
        token: str,
        *,
        nonce: str | None = None,
        provider: str | None = None,
    ) -> VerifiedToken:
        """The verified claims, else ``TokenRejectedError`` naming the failed check.

        With ``provider``, the token must come from that provider.
        """
        if not isinstance(token, str) or token.count(".") != 2:
            raise TokenRejectedError("malformed", "Not a signed JWT")
        try:
            header = jwt.get_unverified_header(token)
            unverified = jwt.decode(token, options={"verify_signature": False})
        except (jwt.InvalidTokenError, json.JSONDecodeError, ValueError) as exc:
            raise TokenRejectedError("malformed", str(exc)) from exc

        issuer = unverified.get("iss")
        keys = self._by_issuer.get(issuer) if isinstance(issuer, str) else None
        if keys is None:
            raise TokenRejectedError(
                "unknown_issuer", f"No provider is configured for issuer {issuer!r}"
            )
        configured = keys.provider
        if provider is not None and configured.name != provider:
            raise TokenRejectedError(
                "unknown_issuer",
                f"The token is from {configured.name}, not {provider}",
            )

        algorithm = header.get("alg")
        if algorithm not in ALLOWED_ALGORITHMS:
            raise TokenRejectedError(
                "algorithm", f"Algorithm {algorithm!r} is not accepted"
            )
        kid = header.get("kid")
        if kid is not None and not isinstance(kid, str):
            raise TokenRejectedError("malformed", "The key id is not a string")
        signing_key = keys.key(kid, algorithm)

        try:
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=[algorithm],
                # Times are checked below, against this verifier's clock.
                options={
                    "verify_aud": False,
                    "verify_exp": False,
                    "verify_nbf": False,
                    "verify_iat": False,
                    "verify_iss": False,
                },
            )
        except jwt.InvalidSignatureError as exc:
            raise TokenRejectedError("invalid_signature", str(exc)) from exc
        except jwt.InvalidTokenError as exc:
            raise TokenRejectedError("malformed", str(exc)) from exc

        if claims.get("iss") != configured.issuer:
            raise TokenRejectedError("unknown_issuer", "The issuer does not match")
        subject = claims.get("sub")
        if not isinstance(subject, str) or not subject:
            raise TokenRejectedError("missing_claim", "The token has no sub")
        audience = _audience(claims.get("aud"))
        if configured.client_id not in audience:
            raise TokenRejectedError(
                "wrong_audience",
                f"The token is not for client {configured.client_id!r}",
            )
        azp = claims.get("azp")
        if (azp is not None or len(audience) > 1) and azp != configured.client_id:
            raise TokenRejectedError(
                "wrong_audience",
                f"The token was issued to {azp!r}, not {configured.client_id!r}",
            )

        now = self._clock()
        expires_at = _int_claim(claims, "exp", required=True)
        issued_at = _int_claim(claims, "iat", required=True)
        not_before = _int_claim(claims, "nbf", required=False)
        if expires_at <= now - self._skew:
            raise TokenRejectedError("expired", "The token has expired")
        if issued_at > now + self._skew or (
            not_before is not None and not_before > now + self._skew
        ):
            raise TokenRejectedError("not_yet_valid", "The token is not valid yet")

        if nonce is not None and claims.get("nonce") != nonce:
            raise TokenRejectedError("nonce_mismatch", "The nonce does not match")

        return VerifiedToken(
            provider=configured.name,
            issuer=configured.issuer,
            subject=subject,
            audience=audience,
            issued_at=issued_at,
            expires_at=expires_at,
            email=_string(claims.get("email")),
            email_verified=_truthy(claims.get("email_verified")),
            display_name=_display_name(claims),
            groups=_groups(claims, configured),
            nonce=_string(claims.get("nonce")),
            session_id=_string(claims.get("sid")),
            claims=claims,
        )


def _audience(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        return (value,)
    if isinstance(value, list) and all(isinstance(v, str) for v in value):
        return tuple(value)
    raise TokenRejectedError("missing_claim", "The token has no audience")


def _int_claim(claims: Mapping[str, Any], name: str, *, required: bool) -> Any:
    value = claims.get(name)
    if value is None and not required:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TokenRejectedError("missing_claim", f"The token has no numeric {name}")
    return int(value)


def _string(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None


def _truthy(value: Any) -> bool:
    # Some providers send the string "true".
    return value is True or (isinstance(value, str) and value.lower() == "true")


def _display_name(claims: Mapping[str, Any]) -> str | None:
    name = _string(claims.get("name"))
    if name:
        return name
    given = " ".join(
        part
        for part in (
            _string(claims.get("given_name")),
            _string(claims.get("family_name")),
        )
        if part
    )
    return given or _string(claims.get("preferred_username"))


def _groups(claims: Mapping[str, Any], provider: IdentityProvider) -> tuple[str, ...]:
    """The provider's groups claim: a top-level claim, else a dotted path
    (``realm_access.roles``)."""
    name = provider.groups_claim
    if not name:
        return ()
    if name in claims:
        return claim_values(claims[name])
    value: Any = claims
    for part in name.split("."):
        if not isinstance(value, Mapping) or part not in value:
            return ()
        value = value[part]
    return claim_values(value)
