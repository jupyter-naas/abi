"""The service token a module presents on every NATS call.

A module signs its own tokens with its **module key** (``ABI_MODULE_KEY``), which the
project derives from its secret for one identity, the module id: ``abi module key
<module_id>`` prints it. The engine accepts such a token only for that identity, and never
for one of its own (``api``, ``engine``), so a module cannot speak for another module or
for Nexus (docs/adr/20261014_module-identities.md). Modules never receive the project
secret itself.

A token the module sends to another module (an agent, a model, an app) is bound to the
instance it calls (``aud``) and lasts five minutes, so the receiver cannot replay it
elsewhere: ``Transport`` asks for it with ``for_audience``. A bound token is reused only
in its first 30 seconds, so it reaches the module with at least 4.5 minutes left: a
call may wait that long in the module's queue before it is authorized.

The token is the engine's service JWT (HS256, claims ``sub``/``iat``/``exp`` and ``aud``
when bound, header ``kid: "module"``), signed here with the standard library: no ABI core,
no JWT library.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from collections.abc import Callable, Mapping

# One hour, like the engine's tokens; refreshed at half of it.
TTL_SECONDS = 3600
# A token bound to one module instance (nats_auth.BOUND_TTL is this one), handed out
# again only in its first BOUND_REUSE_SECONDS: it always arrives with at least
# BOUND_TTL_SECONDS - BOUND_REUSE_SECONDS left, longer than callers wait for an answer.
BOUND_TTL_SECONDS = 300
BOUND_REUSE_SECONDS = 30
MAX_AUDIENCES = 1024
# The header naas_abi_core.engine.nats_auth checks module tokens by.
MODULE_KEY_ID = "module"


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


class TokenCache:
    """Tokens by audience (None: unbound), each signed by ``sign(audience,
    issued_at, ttl_seconds)`` and handed out again only while younger than its
    reuse window. ``ModuleToken`` and the engine's ``ServiceTokenSource`` share it."""

    def __init__(
        self,
        sign: Callable[[str | None, int, int], str],
        *,
        ttl_seconds: int = TTL_SECONDS,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.sign, self.ttl, self.clock = sign, ttl_seconds, clock
        self._tokens: dict[str | None, tuple[float, str]] = {}

    def unbound(self) -> str:
        return self._get(None, self.ttl, self.ttl / 2)

    def bound(self, audience: str) -> str:
        if not audience:
            raise ValueError("audience must be a non-empty string")
        ttl = min(self.ttl, BOUND_TTL_SECONDS)
        return self._get(audience, ttl, min(BOUND_REUSE_SECONDS, ttl / 2))

    def _get(self, audience: str | None, ttl: int, reuse: float) -> str:
        now = self.clock()
        cached = self._tokens.get(audience)
        if cached is not None and now - cached[0] < reuse:
            return cached[1]
        if len(self._tokens) >= MAX_AUDIENCES:
            self._tokens.clear()
        token = self.sign(audience, int(now), ttl)
        self._tokens[audience] = (now, token)
        return token


class ModuleToken:
    """Token source (``run_module(token=...)``): ``token()`` for the engine's services,
    ``token.for_audience(instance_id)`` for a call to another module, both for
    ``identity``, signed with its module ``key``, refreshed at half their lifetime."""

    def __init__(
        self,
        identity: str,
        key: str,
        *,
        ttl_seconds: int = TTL_SECONDS,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if not identity:
            raise ValueError("identity must be a non-empty string")
        if not key:
            raise ValueError("a module token needs its module key")
        self.identity, self.key = identity, key
        self._cache = TokenCache(
            lambda audience, issued_at, ttl: self._sign(issued_at, ttl, audience),
            ttl_seconds=ttl_seconds,
            clock=clock,
        )

    def __call__(self) -> str:
        return self._cache.unbound()

    def for_audience(self, audience: str) -> str:
        return self._cache.bound(audience)

    def _sign(self, issued_at: int, ttl: int, audience: str | None = None) -> str:
        header = _b64(
            json.dumps(
                {"alg": "HS256", "kid": MODULE_KEY_ID, "typ": "JWT"},
                separators=(",", ":"),
            ).encode()
        )
        claims: dict[str, object] = {
            "sub": self.identity,
            "iat": issued_at,
            "exp": issued_at + ttl,
        }
        if audience is not None:
            claims["aud"] = audience
        payload = _b64(json.dumps(claims, separators=(",", ":")).encode())
        signature = hmac.new(
            self.key.encode(), f"{header}.{payload}".encode(), hashlib.sha256
        ).digest()
        return f"{header}.{payload}.{_b64(signature)}"


def token_from_env(env: Mapping[str, str], identity: str) -> str | ModuleToken:
    """A :class:`ModuleToken` for ``identity`` signed with ``ABI_MODULE_KEY``, else
    ``ABI_SERVICE_TOKEN`` (an issued token, used as is). The key wins when both are
    set: it signs fresh tokens, and only it can bind one to the module a call goes to;
    an issued token expires, and cannot call another module."""
    key = env.get("ABI_MODULE_KEY", "")
    if key:
        return ModuleToken(identity, key)
    issued = env.get("ABI_SERVICE_TOKEN", "")
    if not issued:
        raise RuntimeError(
            f"Set ABI_MODULE_KEY to the module key of {identity!r} "
            f"(`abi module key {identity}` in the project), or ABI_SERVICE_TOKEN."
        )
    return issued
