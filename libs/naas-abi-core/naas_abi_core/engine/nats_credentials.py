"""Credentials of core processes: where their tokens and their JWKS come from.

* The serving engine holds IAM: it signs its own tokens (``issuer_source``)
  and verifies against its own JWKS (``IAMService.verifier``), no NATS hop.
* Any other core process (a client-role engine, a ``nats_rpc`` adapter
  calling another deployment) holds a service key: ``service_key_source``
  exchanges it at ``abi.iam.v1.token`` and ``nats_verifier`` reads the JWKS
  at ``abi.iam.v1.jwks``. Neither needs credentials: each opens a short
  connection of its own.

See docs/specs/rfcs/20261013_identity-and-authorization.md, §8.2 and §9.1.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable, Iterable
from typing import TYPE_CHECKING, Any

from naas_abi_core.engine.nats_naming import connection_name

# nats, the tokens, the runtime and the protos load on first use: the
# configuration imports this module, and core without the NATS extra loads it.

if TYPE_CHECKING:
    from naas_abi_core.engine.nats_auth import (
        IssuedToken,
        JWKSVerifier,
        RenewingTokenSource,
    )
    from naas_abi_core.services.iam.IAMService import IAMService


NATS_AUDIENCE = "abi:nats"


def _auth() -> Any:
    from naas_abi_core.engine import nats_auth

    return nats_auth


def KeyExchangeError(message: str) -> Exception:
    """The engine refused the key, or could not be asked (an
    ``InvalidServiceTokenError``)."""
    return _auth().InvalidServiceTokenError(message)


def _run(coro: Any, timeout: float) -> Any:
    from naas_abi_core.engine import nats_runtime

    return nats_runtime.run_coro(coro, timeout=timeout)


def _pb() -> Any:
    from naas_abi_proto.iam.v1 import iam_pb2

    return iam_pb2


async def _ask(nats_url: str, subject: str, payload: bytes, timeout: float) -> bytes:
    import nats

    nc = await nats.connect(
        nats_url,
        name=connection_name("abi-credentials"),
        allow_reconnect=False,
        connect_timeout=timeout,
    )
    try:
        # Bounded by construction: a key, or nothing.
        reply = await nc.request(subject, payload, timeout=timeout)
        return reply.data
    finally:
        await nc.close()


def exchange_key(
    nats_url: str,
    key: str,
    *,
    timeout: float = 10.0,
    audience: str = NATS_AUDIENCE,
) -> IssuedToken:
    """An access token for ``key`` (``abi.iam.v1.token``): ``abi:nats`` for
    the kernel services, or ``abi:host:<recipient>`` for one module host."""
    auth = _auth()
    auth.parse_key(key)  # a malformed key never leaves the process
    pb = _pb()
    request = pb.TokenRequest(key=key, audience=audience).SerializeToString()
    try:
        data = _run(_ask(nats_url, auth.TOKEN_SUBJECT, request, timeout), timeout + 5)
    except Exception as exc:
        raise KeyExchangeError(f"cannot exchange the service key: {exc}") from exc
    response = pb.TokenResponse.FromString(data)
    if response.HasField("error"):
        raise KeyExchangeError(
            f"key exchange refused ({response.error.code}): {response.error.message}"
        )
    return auth.IssuedToken(
        response.access_token,
        time.time() + response.expires_in,
        response.principal_id,
        response.name,
    )


def service_key_source(
    nats_url: str,
    key: str,
    *,
    identity: str | None = None,
    timeout: float = 10.0,
    audience: str = NATS_AUDIENCE,
) -> RenewingTokenSource:
    """A token source exchanging ``key``, renewed at half the token's life.

    ``identity`` names the source before the first exchange (connection
    names); it defaults to the key id.
    """
    auth = _auth()
    _, key_id, _ = auth.parse_key(key)
    return auth.RenewingTokenSource(
        identity or f"key:{key_id}",
        lambda: exchange_key(nats_url, key, timeout=timeout, audience=audience),
    )


def jwks_over_nats(
    nats_url: str, *, timeout: float = 10.0
) -> Callable[[], dict[str, Any]]:
    def fetch() -> dict[str, Any]:
        pb = _pb()
        data = _run(
            _ask(
                nats_url,
                _auth().JWKS_SUBJECT,
                pb.JwksRequest().SerializeToString(),
                timeout,
            ),
            timeout + 5,
        )
        response = pb.JwksResponse.FromString(data)
        if response.HasField("error"):
            raise _auth().InvalidServiceTokenError(response.error.message)
        return json.loads(response.jwks_json)

    return fetch


def nats_verifier(
    nats_url: str, *, audiences: Iterable[str] = (NATS_AUDIENCE,)
) -> JWKSVerifier:
    """A verifier for a process without IAM: the JWKS comes over NATS."""
    return _auth().JWKSVerifier(jwks_over_nats(nats_url), audiences=audiences)


# The accounts a user may be delegated by: the engine's own, which verified the
# user themselves (RFC §10.2).
DELEGATING_ACCOUNTS = ("api", "engine")
_HOST_ULID = re.compile(r"[0-9a-z]{26}")


class DelegationError(Exception):
    """A call for a user that cannot carry the user: it is not made as the
    account alone, which would widen it."""


def delegation(iam: Any, identity: str) -> Callable[[Any, str | None], IssuedToken]:
    """What a first-party ``identity`` calls to carry a user it verified: a
    token exchange for ``abi:delegated:agent`` (RFC §9.4), as ``identity``.

    Without ``recipient`` the token acts as ``identity`` itself, for the kernel
    services; with one (a call to the module host whose subjects carry that
    ``<sa>``) it names the module as the actor: a host that keeps it holds
    only what that module may do for the user."""
    from naas_abi_core.engine.call_context import as_service_account
    from naas_abi_core.services.iam.IAMPorts import TOKEN_TYPE_SESSION, TokenExchange
    from naas_abi_core.services.iam.names import resource_name

    def delegate(user: Any, recipient: str | None = None) -> IssuedToken:
        resource = None
        if recipient is not None:
            if not _HOST_ULID.fullmatch(recipient):
                raise DelegationError(f"{recipient!r} is not a module host")
            resource = resource_name("iam", "principal", f"sa_{recipient}")
        request = TokenExchange(
            subject_token=user.id,
            subject_token_type=TOKEN_TYPE_SESSION,
            audience=_auth().AGENT_AUDIENCE,
            resource=resource,
            groups=tuple(sorted(user.groups)),
        )
        # As the account: the exchange is its own, never the signed-in user's.
        with as_service_account(identity):
            return iam.exchange_token(request)

    return delegate


def issuer_source(
    iam: IAMService, name: str, audience: str = NATS_AUDIENCE
) -> RenewingTokenSource:
    """Tokens of the engine's own service account ``name``, signed in process,
    for ``audience`` (``abi:host:<recipient>`` for the calls it makes to one module
    host). ``api`` and ``engine`` carry the users they serve in a delegation
    (``token_for``); a host token is the account's own."""
    delegates = audience == NATS_AUDIENCE and name in DELEGATING_ACCOUNTS
    return _auth().RenewingTokenSource(
        name,
        lambda: iam.issue_service_token(name, audience=audience),
        delegate=delegation(iam, name) if delegates else None,
    )


def rpc_client(cls: Any, nats_url: str, service_key: str, **options: Any) -> Any:
    """A ``NatsRPCClient`` subclass calling another deployment's engine as the
    service account ``service_key`` belongs to (a ``nats_rpc`` adapter)."""
    return cls(nats_url, service_key_source(nats_url, service_key), **options)
