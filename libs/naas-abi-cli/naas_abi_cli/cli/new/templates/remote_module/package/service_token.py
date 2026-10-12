"""The service token this module presents on every NATS call.

``ABI_SERVICE_TOKEN``, when set, is used as is: ``abi dev up`` issues one for
each dev module. Otherwise the module signs its own from ``NATS_JWT_SECRET``,
the project's shared secret, and refreshes it at half its lifetime. The token
is the engine's Stage 1 service JWT (HS256, claims ``sub``/``iat``/``exp``, as
``naas_abi_core.engine.nats_auth`` issues), signed here with the standard
library so the module needs neither ABI core nor a JWT library. ``sub`` stays
the same across refreshes: discovery uses it as the owner of the registration.

(Not ``token.py``: that would shadow the standard library's ``token`` module.)
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


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


class ServiceToken:
    """Callable token source for ``naas_abi_sdk`` (``run_module(token=...)``)."""

    def __init__(
        self,
        identity: str,
        secret: str,
        *,
        ttl_seconds: int = TTL_SECONDS,
        clock: Callable[[], float] = time.time,
    ) -> None:
        if not identity:
            raise ValueError("identity must be a non-empty string")
        self.identity, self.secret = identity, secret
        self.ttl, self.clock = ttl_seconds, clock
        self._token, self._issued = "", float("-inf")

    def __call__(self) -> str:
        now = self.clock()
        if now - self._issued >= self.ttl / 2:
            self._token, self._issued = self._sign(int(now)), now
        return self._token

    def _sign(self, issued_at: int) -> str:
        header = _b64(
            json.dumps({"alg": "HS256", "typ": "JWT"}, separators=(",", ":")).encode()
        )
        claims = {"sub": self.identity, "iat": issued_at, "exp": issued_at + self.ttl}
        payload = _b64(json.dumps(claims, separators=(",", ":")).encode())
        signature = hmac.new(
            self.secret.encode(), f"{header}.{payload}".encode(), hashlib.sha256
        ).digest()
        return f"{header}.{payload}.{_b64(signature)}"


def token_source(env: Mapping[str, str], identity: str) -> str | ServiceToken:
    """``ABI_SERVICE_TOKEN`` if set, else a token signed from ``NATS_JWT_SECRET``."""
    issued = env.get("ABI_SERVICE_TOKEN", "")
    if issued:
        return issued
    secret = env.get("NATS_JWT_SECRET", "")
    if not secret:
        raise RuntimeError(
            "Set ABI_SERVICE_TOKEN, or NATS_JWT_SECRET (the project's .env) "
            "for the module to sign its own service token."
        )
    return ServiceToken(identity, secret)
