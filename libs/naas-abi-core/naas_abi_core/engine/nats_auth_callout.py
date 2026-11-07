"""The broker's auth callout, answered by the serving engine.

``nats.conf`` declares two static users, ``engine`` and ``auth``, exempt from
the callout, and ``auth_callout { issuer: <account public key> }``. Every other
connection logs in as user ``sa`` with a service key as its password; the
broker asks ``$SYS.REQ.USER.AUTH`` and this responder, logged in as ``auth``:

1. checks the key and its principal (``IAMService.authenticate_key``: revoked,
   expired or suspended is refused at once);
2. derives the subjects the account's policy allows (``broker_permissions``);
3. answers with a user JWT signed by the account seed, valid five minutes by
   default (ten at most, the life of an access token) and never past the key's
   expiry, without response permissions (a module answers on ``_INBOX.>``).
   A reconnect recomputes it: the SDK reconnects every two minutes, so a
   revoked key, a suspended account or a narrowed policy takes effect at the
   broker within the JWT's life, and the connection ends there (nats-py does
   not reconnect a connection the broker expired).

The streams and consumers a module uses are created by the engine on demand
(``nats_broker_control.py``). Each request is answered on its own task: one
slow login holds up no other.

Resource-level decisions stay in the domain services.
"""

from __future__ import annotations

import asyncio
import time
from datetime import UTC, datetime
from typing import Any

import nats
from naas_abi_core import logger
from naas_abi_core.engine.nats_naming import connection_name
from naas_abi_core.engine.nats_nkeys import (
    PREFIX_SERVER,
    KeyPair,
    NKeyError,
    decode_jwt,
    encode_jwt,
)
from naas_abi_core.services.iam.broker import BrokerPermissions
from naas_abi_core.services.iam.IAMPorts import IAMError, KeyRefusedError
from naas_abi_core.services.iam.IAMService import IAMService

AUTH_SUBJECT = "$SYS.REQ.USER.AUTH"
# The user name a service key logs in with; the key is the password.
KEY_USER = "sa"
# NATS's global account: the one a broker without accounts puts every user in.
ACCOUNT = "$G"
# How long a connection's permissions last: never longer than an access token.
# naas_abi_sdk.credentials.CONNECTION_TTL_SECONDS names the same bounds (a
# test keeps them equal).
DEFAULT_USER_TTL_SECONDS = 300
MAX_USER_TTL_SECONDS = 600


class AuthCallout:
    def __init__(
        self,
        iam: IAMService,
        issuer_seed: str,
        nats_url: str,
        *,
        user_ttl_seconds: int = DEFAULT_USER_TTL_SECONDS,
    ) -> None:
        self.iam = iam
        self.issuer = KeyPair.from_seed(issuer_seed)
        self.nats_url = nats_url
        self.user_ttl_seconds = min(user_ttl_seconds, MAX_USER_TTL_SECONDS)
        self._nc: Any = None
        self._tasks: set[asyncio.Task] = set()

    @property
    def issuer_public_key(self) -> str:
        return self.issuer.public_key

    async def start(self) -> None:
        self._nc = await nats.connect(
            self.nats_url, name=connection_name("abi-engine:auth-callout")
        )
        await self._nc.subscribe(AUTH_SUBJECT, cb=self._handle)
        await self._nc.flush()
        logger.info(
            f"NATS auth callout answered by this engine ({self.issuer_public_key})"
        )

    async def stop(self) -> None:
        nc, self._nc = self._nc, None
        if nc is not None:
            await nc.drain()
        for task in list(self._tasks):
            task.cancel()

    async def _handle(self, msg: Any) -> None:
        task = asyncio.create_task(self._serve(msg))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)

    async def _serve(self, msg: Any) -> None:
        try:
            request = decode_jwt(msg.data.decode(), issuer_prefix=PREFIX_SERVER)
        except (NKeyError, UnicodeDecodeError) as exc:
            logger.warning(f"Auth callout: unreadable request refused ({exc})")
            return
        answer, _ = await asyncio.to_thread(self._answer, request)
        # Bounded by construction: one signed JWT naming the subjects of one policy.
        await msg.respond(answer.encode())

    def answer(self, request: dict[str, Any]) -> str:
        """The signed authorization response to a server's request."""
        return self._answer(request)[0]

    def _answer(self, request: dict[str, Any]) -> tuple[str, BrokerPermissions | None]:
        claims = request.get("nats", {})
        user_nkey = str(claims.get("user_nkey", ""))
        server = str((claims.get("server_id") or {}).get("id", ""))
        options = claims.get("connect_opts") or {}
        permissions: BrokerPermissions | None = None
        try:
            user_jwt, permissions = self._admit(user_nkey, options)
            body: dict[str, Any] = {"jwt": user_jwt}
        except KeyRefusedError:
            logger.info(
                f"Auth callout: refused a connection as {options.get('user')!r} "
                f"from {(claims.get('client_info') or {}).get('host', '?')}"
            )
            body = {"error": "invalid service key"}
        except IAMError as exc:
            logger.warning(f"Auth callout: refused a connection: {exc}")
            body = {"error": "not authorized"}
        except Exception as exc:  # noqa: BLE001 - a store error must still be answered
            # Unanswered, the server holds the connection until its own timeout.
            # The type only, never the traceback or the message: the frames
            # hold the service key the connection logged in with.
            logger.error(
                "Auth callout: could not decide a connection; refused "
                f"({type(exc).__name__})"
            )
            body = {"error": "not authorized"}
        response = encode_jwt(
            {
                "sub": user_nkey,
                "aud": server,
                "nats": {**body, "type": "authorization_response", "version": 2},
            },
            self.issuer,
        )
        return response, permissions

    def _admit(
        self, user_nkey: str, options: dict[str, Any]
    ) -> tuple[str, BrokerPermissions]:
        if options.get("user") != KEY_USER or not options.get("pass"):
            raise KeyRefusedError()
        principal, key = self.iam.authenticate_key(str(options["pass"]))
        permissions = self.iam.broker_permissions(principal, key)
        expires = time.time() + self.user_ttl_seconds
        if key.expires_at is not None:
            expires = min(expires, key.expires_at.timestamp())
        if expires <= time.time():
            raise KeyRefusedError()
        logger.debug(
            f"Auth callout: {principal.name} ({principal.id}) connected with key "
            f"{key.key_id} until {datetime.fromtimestamp(expires, UTC):%H:%M:%S}"
        )
        user = encode_jwt(
            {
                "sub": user_nkey,
                "aud": ACCOUNT,
                "name": principal.name or principal.id,
                "exp": int(expires),
                "nats": {
                    "pub": {"allow": list(permissions.publish)},
                    "sub": {"allow": list(permissions.subscribe)},
                    # No "resp": response permissions would let a module answer
                    # any reply subject of a message it receives, and it picks
                    # the reply subject of what it sends itself.
                    "subs": -1,
                    "data": -1,
                    "payload": -1,
                    "type": "user",
                    "version": 2,
                },
            },
            self.issuer,
        )
        return user, permissions
