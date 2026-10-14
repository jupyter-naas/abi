"""The service token a module presents on every NATS call.

A module signs its own tokens with its **module key** (``ABI_MODULE_KEY``), which the
project derives from its secret for one identity, the module id: ``abi module key
<module_id>`` prints it. The engine accepts such a token only for that identity, and never
for one of its own (``api``, ``engine``), so a module cannot speak for another module or
for Nexus (docs/adr/20261014_module-identities.md). Modules never receive the project
secret itself.

The token is the engine's service JWT (HS256, claims ``sub``/``iat``/``exp``, header
``kid: "module"``), signed here with the standard library: no ABI core, no JWT library.
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
# The header naas_abi_core.engine.nats_auth checks module tokens by.
MODULE_KEY_ID = "module"


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


class ModuleToken:
    """Callable token source (``run_module(token=...)``): a token for ``identity``,
    signed with its module ``key``, refreshed at half its lifetime."""

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
        self._token, self._issued = "", float("-inf")

    def __call__(self) -> str:
        now = self.clock()
        if now - self._issued >= self.ttl / 2:
            self._token, self._issued = self._sign(int(now)), now
        return self._token

    def _sign(self, issued_at: int) -> str:
        header = _b64(
            json.dumps(
                {"alg": "HS256", "kid": MODULE_KEY_ID, "typ": "JWT"},
                separators=(",", ":"),
            ).encode()
        )
        claims = {"sub": self.identity, "iat": issued_at, "exp": issued_at + self.ttl}
        payload = _b64(json.dumps(claims, separators=(",", ":")).encode())
        signature = hmac.new(
            self.key.encode(), f"{header}.{payload}".encode(), hashlib.sha256
        ).digest()
        return f"{header}.{payload}.{_b64(signature)}"


def token_from_env(env: Mapping[str, str], identity: str) -> str | ModuleToken:
    """``ABI_SERVICE_TOKEN`` if set (an issued token, used as is), else a
    :class:`ModuleToken` for ``identity`` signed with ``ABI_MODULE_KEY``."""
    issued = env.get("ABI_SERVICE_TOKEN", "")
    if issued:
        return issued
    key = env.get("ABI_MODULE_KEY", "")
    if not key:
        raise RuntimeError(
            f"Set ABI_MODULE_KEY to the module key of {identity!r} "
            f"(`abi module key {identity}` in the project), or ABI_SERVICE_TOKEN."
        )
    return ModuleToken(identity, key)
