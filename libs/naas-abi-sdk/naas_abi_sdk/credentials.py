"""A module's credential: its service key, exchanged for engine tokens.

A module holds a service key (``ABI_SERVICE_KEY``, ``abi_sk_<key id>_<secret>``)
and no signing secret (docs/specs/rfcs/20261013_identity-and-authorization.md,
§8):

* it logs in to the broker with it (user ``sa``, the key as password), and the
  engine's auth callout gives the connection the subjects its approved policy
  allows. Replies come under ``_INBOX.<key id>``, an inbox prefix only this
  key's connections may read;
* it exchanges it at ``abi.iam.v1.token`` for an access token (ten minutes at
  most), sent on every call, and exchanges again at half its life.

Revoking the key ends the next exchange and the next connection; tokens
already issued expire within ten minutes, and the broker's permissions of a
connection within five (the transport reconnects every two minutes).
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any

from naas_abi_proto.iam.v1 import iam_pb2 as pb

if TYPE_CHECKING:
    from naas_abi_sdk.transport import Transport

# The broker gives a connection its subjects for at most this long (the engine's
# auth callout: nats_auth_callout.MAX_USER_TTL_SECONDS, five minutes by
# default, never under four). nats-py does not reconnect a connection the
# broker expired, so a transport reconnects itself well before: the callout
# then computes its subjects again.
CONNECTION_TTL_SECONDS = 600
RENEW_CONNECTION_SECONDS = 120.0
TOKEN_SUBJECT = "abi.iam.v1.token"
KEY_USER = "sa"
SERVICE_KEY_PREFIX = "abi_sk_"


class ServiceKey:
    def __init__(self, value: str) -> None:
        key_id, sep, secret = value.removeprefix(SERVICE_KEY_PREFIX).partition("_")
        if (
            not value.startswith(SERVICE_KEY_PREFIX)
            or not sep
            or not secret
            or len(key_id) != 16
            or not key_id.isalnum()
        ):
            raise ValueError("ABI_SERVICE_KEY must be a service key (abi_sk_...)")
        self.value = value
        self.key_id = key_id
        self._token = ""
        self._renew_at = 0.0
        self._expires_at = 0.0
        self._lock: asyncio.Lock | None = None
        # Known after the first exchange: the account the key belongs to.
        self.principal_id = ""
        self.name = ""

    def __repr__(self) -> str:
        return f"ServiceKey({self.key_id})"

    @property
    def inbox_prefix(self) -> str:
        return f"_INBOX.{self.key_id}"

    def connect_options(self) -> dict[str, Any]:
        """nats-py ``connect`` options logging in with this key."""
        return {
            "user": KEY_USER,
            "password": self.value,
            "inbox_prefix": self.inbox_prefix,
        }

    async def access_token(self, transport: Transport) -> str:
        """A token valid a few more minutes, exchanged when half its life is gone."""
        if self._lock is None:
            self._lock = asyncio.Lock()
        async with self._lock:
            if self._token and time.time() < self._renew_at:
                return self._token
            try:
                await self._exchange(transport)
            except Exception:
                if self._token and time.time() < self._expires_at - 5:
                    return self._token  # the engine may be restarting
                raise
            return self._token

    def invalidate(self) -> None:
        self._renew_at = 0.0

    async def _exchange(self, transport: Transport) -> None:
        from naas_abi_sdk.transport import RPCError

        nc = await transport.connect()
        started = time.time()
        # Bounded by construction: the key, then one token.
        reply = await nc.request(
            TOKEN_SUBJECT,
            pb.TokenRequest(key=self.value).SerializeToString(),
            timeout=transport.timeout,
        )
        response = pb.TokenResponse.FromString(reply.data)
        if response.HasField("error") and response.error.code:
            raise RPCError(response.error.code, response.error.message)
        lifetime = max(1, response.expires_in)
        self._token = response.access_token
        self._expires_at = started + lifetime
        self._renew_at = started + lifetime / 2
        self.principal_id, self.name = response.principal_id, response.name


def module_account(name: str) -> tuple[str, str] | None:
    """``(project, module_id)`` of a module's service account name
    (``module/<project>/<module_id>``), else None."""
    parts = name.split("/")
    if len(parts) == 3 and parts[0] == "module" and parts[1] and parts[2]:
        return parts[1], parts[2]
    return None
