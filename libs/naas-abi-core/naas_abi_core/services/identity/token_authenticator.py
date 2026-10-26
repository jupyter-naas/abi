"""What IAM asks of the identity service to exchange an IdP's token.

A relying party that holds an IdP's ID token exchanges it for an ``abi:session``
token (``IAMService.exchange_token``). IAM holds no reference to the identity
service (the engine loads identity right after IAM, §11.1), so the engine hands
it this adapter: it verifies the token against the configured provider
(``identity.authenticate``: issuer, signature, audience, expiry, nonce-less),
resolves or creates the IAM user, refuses a suspended one and maps the groups
claim. The requester decides whether the provider may be used at all
(``identity:Authenticate``), as for any caller of the identity service: IAM
checks ``iam:ExchangeToken`` of the same requester first.
"""

from __future__ import annotations

from dataclasses import replace

from naas_abi_core.engine.call_context import current_call_context, use_call_context
from naas_abi_core.engine.nats_auth import InvalidServiceTokenError
from naas_abi_core.services.iam.IAMPorts import IdentityAuthenticator, KeyRefusedError
from naas_abi_core.services.identity.IdentityPorts import (
    IdentityError,
    IIdentityService,
    PrincipalSuspendedError,
)


class IdentityTokenAuthenticator(IdentityAuthenticator):
    def __init__(self, identity: IIdentityService) -> None:
        self._identity = identity

    def authenticate_token(
        self, token: str, token_type: str
    ) -> tuple[str, tuple[str, ...]]:
        # The requester alone is checked: the user it may act for does not hold
        # identity:Authenticate, and is not the one authenticating.
        context = replace(current_call_context(), on_behalf_of=None)
        try:
            with use_call_context(context):
                authenticated = self._identity.authenticate(token)
        except PrincipalSuspendedError:
            raise KeyRefusedError() from None  # one message, whatever the cause
        except IdentityError as exc:
            raise InvalidServiceTokenError(str(exc)) from exc
        return authenticated.principal_id, tuple(authenticated.group_ids)
