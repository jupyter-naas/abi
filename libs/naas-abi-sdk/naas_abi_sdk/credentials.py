"""A module's credential: its service key, exchanged for engine tokens.

A module holds a service key (``ABI_SERVICE_KEY``, ``abi_sk_<key id>_<secret>``)
and no signing secret:

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
EXCHANGE_SUBJECT = "abi.iam.v1.exchange_token"
KEY_USER = "sa"
NATS_AUDIENCE = "abi:nats"
# A module acting for a user: what a host is handed to call the
# kernel with for the user it serves, and renews (up to eight hours).
AGENT_AUDIENCE = "abi:delegated:agent"
TOKEN_EXCHANGE_GRANT = "urn:ietf:params:oauth:grant-type:token-exchange"
TOKEN_TYPE_JWT = "urn:ietf:params:oauth:token-type:jwt"
# A token for one module host this module calls (an agent, a model, an app):
# ``abi:host:<the host's subject token>``, the ``<sa>`` of its subjects. The
# kernel services refuse it and discovery accepts it from that host only, so a
# host that keeps it can use it nowhere else.
HOST_AUDIENCE_PREFIX = "abi:host:"
MAX_AUDIENCES = 256


def host_audience(recipient: str) -> str:
    return HOST_AUDIENCE_PREFIX + recipient


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
        # One token per audience: [token, renew at, expires at].
        self._tokens: dict[str, list[Any]] = {}
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

    async def access_token(
        self, transport: Transport, audience: str = NATS_AUDIENCE
    ) -> str:
        """A token valid a few more minutes, exchanged when half its life is
        gone. ``audience``: ``abi:nats`` for the kernel services,
        ``host_audience(<sa>)`` for the one module host it calls (it holds the
        token, so it is good nowhere else)."""
        if self._lock is None:
            self._lock = asyncio.Lock()
        async with self._lock:
            token, renew_at, expires_at = self._tokens.get(audience, ["", 0.0, 0.0])
            if token and time.time() < renew_at:
                return token
            try:
                await self._exchange(transport, audience)
            except Exception:
                if token and time.time() < expires_at - 5:
                    return token  # the engine may be restarting
                raise
            if len(self._tokens) > MAX_AUDIENCES:  # one per host called
                now = time.time()
                for key in [k for k, v in self._tokens.items() if v[2] < now]:
                    del self._tokens[key]
            return self._tokens[audience][0]

    async def renew_delegation(self, transport: Transport, token: str) -> str:
        """A fresh ``abi:delegated:agent`` token for the delegation ``token``
        that this module holds: IAM renews it for the module it names, until
        eight hours after it began. Sent with the module's own token, so the
        exchange is the module's, never the user's."""
        from naas_abi_sdk.transport import RPCError

        own = await self.access_token(transport)
        nc = await transport.connect()
        reply = await nc.request(
            EXCHANGE_SUBJECT,
            pb.ExchangeTokenRequest(
                grant_type=TOKEN_EXCHANGE_GRANT,
                subject_token=token,
                subject_token_type=TOKEN_TYPE_JWT,
                audience=AGENT_AUDIENCE,
            ).SerializeToString(),
            headers={"Nats-Auth-Token": own},
            timeout=transport.timeout,
        )
        response = pb.ExchangeTokenResponse.FromString(reply.data)
        if response.HasField("error") and response.error.code:
            raise RPCError(response.error.code, response.error.message)
        return response.access_token

    def invalidate(self) -> None:
        for slot in self._tokens.values():
            slot[1] = 0.0

    async def _exchange(self, transport: Transport, audience: str) -> None:
        from naas_abi_sdk.transport import RPCError

        nc = await transport.connect()
        started = time.time()
        # Bounded by construction: the key, then one token.
        reply = await nc.request(
            TOKEN_SUBJECT,
            pb.TokenRequest(key=self.value, audience=audience).SerializeToString(),
            timeout=transport.timeout,
        )
        response = pb.TokenResponse.FromString(reply.data)
        if response.HasField("error") and response.error.code:
            raise RPCError(response.error.code, response.error.message)
        lifetime = max(1, response.expires_in)
        self._tokens[audience] = [
            response.access_token,
            started + lifetime / 2,
            started + lifetime,
        ]
        self.principal_id, self.name = response.principal_id, response.name


def module_account(name: str) -> tuple[str, str] | None:
    """``(project, module_id)`` of a module's service account name
    (``module/<project>/<module_id>``), else None."""
    parts = name.split("/")
    if len(parts) == 3 and parts[0] == "module" and parts[1] and parts[2]:
        return parts[1], parts[2]
    return None
