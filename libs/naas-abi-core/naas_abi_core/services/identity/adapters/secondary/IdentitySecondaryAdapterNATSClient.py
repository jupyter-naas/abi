"""Identity over NATS for engines in the client role: the serving engine's.

Implements ``IIdentityService``, so a client engine's ``services.identity``
behaves like the serving engine's. The serving engine authorizes the caller
its credentials name. Calls are never replayed after a failure: a code is
redeemed once.
"""

from __future__ import annotations

from typing import Any

from naas_abi_proto.identity.v1 import identity_pb2 as pb

from naas_abi_core.engine.nats_rpc import NatsRPCClient
from naas_abi_core.services.identity.adapters import identity_nats_codec as codec
from naas_abi_core.services.identity.IdentityPorts import (
    AuthenticatedUser,
    IIdentityService,
    ProviderInfo,
    ProvisionedUser,
    SignIn,
    VerifiedToken,
)


class IdentitySecondaryAdapterNATSClient(NatsRPCClient, IIdentityService):
    _default: str | None = None
    _default_known = False

    def _request(self, operation: str, **fields: Any) -> Any:
        name = codec.OPERATIONS[operation]
        request = getattr(pb, f"{name}Request")(context=self._context(), **fields)
        response = self._call(
            f"{codec.SUBJECT_PREFIX}.{operation}",
            request,
            getattr(pb, f"{name}Response"),
        )
        if response.HasField("error") and response.error.code:
            codec.raise_for(response.error)
        return response

    # -- providers --------------------------------------------------------------

    def list_providers(self) -> list[ProviderInfo]:
        response = self._request("list_providers")
        self._default = (
            response.default_provider if response.HasField("default_provider") else None
        )
        self._default_known = True
        return [codec.provider_from_pb(p) for p in response.providers]

    def get_provider(self, name: str) -> ProviderInfo:
        return codec.provider_from_pb(self._request("get_provider", name=name).provider)

    @property
    def default_provider(self) -> str | None:
        if not self._default_known:
            self.list_providers()
        return self._default

    # -- tokens -----------------------------------------------------------------

    def verify_token(self, token: str, *, nonce: str | None = None) -> VerifiedToken:
        response = self._request("verify_token", token=token, nonce=nonce)
        return codec.token_from_pb(response.token)

    def authenticate(
        self, token: str, *, nonce: str | None = None
    ) -> AuthenticatedUser:
        response = self._request("authenticate", token=token, nonce=nonce)
        return codec.user_from_pb(response.user)

    # -- a relying party's sign-in ----------------------------------------------

    def authorization_url(
        self,
        provider: str,
        *,
        redirect_uri: str,
        state: str,
        nonce: str,
        code_challenge: str,
        login_hint: str | None = None,
        prompt: str | None = None,
    ) -> str:
        return self._request(
            "authorization_url",
            provider=provider,
            redirect_uri=redirect_uri,
            state=state,
            nonce=nonce,
            code_challenge=code_challenge,
            login_hint=login_hint,
            prompt=prompt,
        ).url

    def exchange_code(
        self,
        provider: str,
        *,
        code: str,
        code_verifier: str,
        redirect_uri: str,
        nonce: str,
    ) -> SignIn:
        response = self._request(
            "exchange_code",
            provider=provider,
            code=code,
            code_verifier=code_verifier,
            redirect_uri=redirect_uri,
            nonce=nonce,
        )
        return codec.sign_in_from_pb(response.sign_in)

    def refresh(
        self, provider: str, *, refresh_token: str, principal_id: str
    ) -> SignIn:
        response = self._request(
            "refresh",
            provider=provider,
            refresh_token=refresh_token,
            principal_id=principal_id,
        )
        return codec.sign_in_from_pb(response.sign_in)

    def revoke(self, provider: str, *, refresh_token: str) -> bool:
        return self._request(
            "revoke", provider=provider, refresh_token=refresh_token
        ).revoked

    def end_session_url(
        self,
        provider: str,
        *,
        id_token_hint: str | None = None,
        post_logout_redirect_uri: str | None = None,
        state: str | None = None,
    ) -> str | None:
        response = self._request(
            "end_session_url",
            provider=provider,
            id_token_hint=id_token_hint,
            post_logout_redirect_uri=post_logout_redirect_uri,
            state=state,
        )
        return response.url if response.HasField("url") else None

    # -- provisioning -----------------------------------------------------------

    def provision_user(
        self, provider: str, email: str, *, name: str | None = None
    ) -> ProvisionedUser:
        response = self._request(
            "provision_user", provider=provider, email=email, name=name
        )
        return codec.provisioned_from_pb(response.user)

    def find_provisioned_user(
        self, provider: str, email: str
    ) -> ProvisionedUser | None:
        response = self._request(
            "find_provisioned_user", provider=provider, email=email
        )
        return (
            codec.provisioned_from_pb(response.user)
            if response.HasField("user")
            else None
        )
