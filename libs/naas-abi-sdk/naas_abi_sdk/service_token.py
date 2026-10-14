"""The service token a module presents on every NATS call.

A module signs its own tokens with its **module key** (``ABI_MODULE_KEY``), which the
project derives from its secret for one identity, the module id: ``abi module key
<module_id>`` prints it. The engine accepts such a token only for that identity, and never
for one of its own (``api``, ``engine``), so a module cannot speak for another module or
for Nexus (docs/adr/20261014_module-identities.md). Modules never receive the project
secret itself.

A token the module sends to another module (an agent, a model, an app) is bound to the
instance it calls (``aud``) and lasts two minutes, so the receiver cannot replay it
elsewhere: ``Transport`` asks for it with ``for_audience``.

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
# A token bound to one module instance, like the engine's (nats_auth.BOUND_TTL).
BOUND_TTL_SECONDS = 120
MAX_AUDIENCES = 1024
# The header naas_abi_core.engine.nats_auth checks module tokens by.
MODULE_KEY_ID = "module"


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


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
        self.ttl, self.clock = ttl_seconds, clock
        self._tokens: dict[str | None, tuple[float, str]] = {}

    def __call__(self) -> str:
        return self._cached(None, self.ttl)

    def for_audience(self, audience: str) -> str:
        if not audience:
            raise ValueError("audience must be a non-empty string")
        return self._cached(audience, min(self.ttl, BOUND_TTL_SECONDS))

    def _cached(self, audience: str | None, ttl: int) -> str:
        now = self.clock()
        cached = self._tokens.get(audience)
        if cached is not None and now - cached[0] < ttl / 2:
            return cached[1]
        if len(self._tokens) >= MAX_AUDIENCES:
            self._tokens.clear()
        token = self._sign(int(now), ttl, audience)
        self._tokens[audience] = (now, token)
        return token

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
