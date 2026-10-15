"""``engine.services.identity``: the engine's OIDC providers (``abi.identity.v1``).

The engine verifies providers' ID tokens and resolves them to IAM users; a
module declares ``identity`` among its services and holds the ``identity:*``
actions it needs (``VerifyToken``, ``Authenticate``, ``SignIn`` on
``abi:-:-:identity:provider/<name>``). Client secrets never leave the engine:
a module acting as a relying party asks the engine to build the authorization
URL, redeem the code and refresh.

Records come back as plain dictionaries.
"""

from __future__ import annotations

from typing import Any

from naas_abi_sdk.services._codec import ServiceProxy


class IdentityService(ServiceProxy):
    domain = "identity"

    async def list_providers(self) -> dict[str, Any]:
        """``{"providers": [...], "default_provider": name | None}``."""
        return await self._request("list_providers")

    async def get_provider(self, name: str) -> dict[str, Any]:
        return await self._request("get_provider", name=name)

    async def verify_token(
        self, token: str, *, nonce: str | None = None
    ) -> dict[str, Any]:
        """The verified token's claims; ``TokenRejected`` names the failed check."""
        return await self._request("verify_token", token=token, nonce=nonce)

    async def authenticate(
        self, token: str, *, nonce: str | None = None
    ) -> dict[str, Any]:
        """``{"principal_id", "token", "group_ids"}``: the token's IAM user."""
        return await self._request("authenticate", token=token, nonce=nonce)

    async def authorization_url(
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
        return await self._request(
            "authorization_url",
            provider=provider,
            redirect_uri=redirect_uri,
            state=state,
            nonce=nonce,
            code_challenge=code_challenge,
            login_hint=login_hint,
            prompt=prompt,
        )

    async def exchange_code(
        self,
        provider: str,
        *,
        code: str,
        code_verifier: str,
        redirect_uri: str,
        nonce: str,
    ) -> dict[str, Any]:
        return await self._request(
            "exchange_code",
            provider=provider,
            code=code,
            code_verifier=code_verifier,
            redirect_uri=redirect_uri,
            nonce=nonce,
        )

    async def refresh(
        self, provider: str, *, refresh_token: str, principal_id: str
    ) -> dict[str, Any]:
        return await self._request(
            "refresh",
            provider=provider,
            refresh_token=refresh_token,
            principal_id=principal_id,
        )

    async def revoke(self, provider: str, *, refresh_token: str) -> bool:
        return await self._request(
            "revoke", provider=provider, refresh_token=refresh_token
        )

    async def end_session_url(
        self,
        provider: str,
        *,
        id_token_hint: str | None = None,
        post_logout_redirect_uri: str | None = None,
        state: str | None = None,
    ) -> str | None:
        return await self._request(
            "end_session_url",
            provider=provider,
            id_token_hint=id_token_hint,
            post_logout_redirect_uri=post_logout_redirect_uri,
            state=state,
        )
