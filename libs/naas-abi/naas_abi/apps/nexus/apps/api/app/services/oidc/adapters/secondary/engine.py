"""The engine's identity and IAM services, as Nexus calls them.

Nexus is the relying party: it calls identity as its own service account
(``api``), never as the user being signed in, who is not authenticated yet.
The engine's services are blocking: each call runs in a worker thread.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any, TypeVar

from naas_abi.apps.nexus.apps.api.app.services.oidc.port import (
    IdentityGateway,
    PrincipalGateway,
)
from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.identity.IdentityPorts import (
    IIdentityService,
    ProviderInfo,
    ProviderUnavailableError,
    SignIn,
)
from starlette.concurrency import run_in_threadpool

NEXUS_IDENTITY = "api"
_T = TypeVar("_T")


async def _as_api(fn: Callable[[], _T]) -> _T:
    def call() -> _T:
        with as_service_account(NEXUS_IDENTITY):
            return fn()

    return await run_in_threadpool(call)


def engine_services() -> Any | None:
    """The loaded engine's services, when Nexus runs in one."""
    try:
        from naas_abi import ABIModule

        return ABIModule.get_instance().engine.services
    except Exception:  # noqa: BLE001 - Nexus alone, or tests
        return None


class EngineIdentityGateway(IdentityGateway):
    def __init__(self, identity: Callable[[], IIdentityService | None]) -> None:
        self._identity = identity

    def _service(self) -> IIdentityService:
        service = self._identity()
        if service is None:
            raise ProviderUnavailableError("The engine's identity service is not loaded")
        return service

    async def providers(self) -> tuple[list[ProviderInfo], str | None]:
        service = self._service()
        return await _as_api(lambda: (service.list_providers(), service.default_provider))

    async def authorization_url(
        self,
        provider: str,
        *,
        redirect_uri: str,
        state: str,
        nonce: str,
        code_challenge: str,
        login_hint: str | None,
    ) -> str:
        service = self._service()
        return await _as_api(
            lambda: service.authorization_url(
                provider,
                redirect_uri=redirect_uri,
                state=state,
                nonce=nonce,
                code_challenge=code_challenge,
                login_hint=login_hint,
            )
        )

    async def exchange_code(
        self,
        provider: str,
        *,
        code: str,
        code_verifier: str,
        redirect_uri: str,
        nonce: str,
    ) -> SignIn:
        service = self._service()
        return await _as_api(
            lambda: service.exchange_code(
                provider,
                code=code,
                code_verifier=code_verifier,
                redirect_uri=redirect_uri,
                nonce=nonce,
            )
        )

    async def refresh(self, provider: str, *, refresh_token: str, principal_id: str) -> SignIn:
        service = self._service()
        return await _as_api(
            lambda: service.refresh(
                provider, refresh_token=refresh_token, principal_id=principal_id
            )
        )

    async def revoke(self, provider: str, *, refresh_token: str) -> bool:
        service = self._service()
        return await _as_api(lambda: service.revoke(provider, refresh_token=refresh_token))

    async def end_session_url(
        self,
        provider: str,
        *,
        id_token_hint: str | None,
        post_logout_redirect_uri: str | None,
    ) -> str | None:
        service = self._service()
        return await _as_api(
            lambda: service.end_session_url(
                provider,
                id_token_hint=id_token_hint,
                post_logout_redirect_uri=post_logout_redirect_uri,
            )
        )


class EngineIAMPrincipals(PrincipalGateway):
    """IAM's principals: suspension checked on every request, cached briefly."""

    def __init__(self, iam: Callable[[], Any | None], *, cache_seconds: float = 5.0) -> None:
        self._iam = iam
        self._cache_seconds = cache_seconds
        self._active: dict[str, tuple[bool, float]] = {}

    async def is_active(self, principal_id: str) -> bool:
        cached = self._active.get(principal_id)
        now = time.monotonic()
        if cached is not None and now - cached[1] < self._cache_seconds:
            return cached[0]
        iam = self._iam()
        if iam is None:
            return False  # no IAM to vouch for the user: fail closed

        def status() -> bool:
            from naas_abi_core.services.iam.IAMPorts import IAMNotFoundError

            try:
                return iam.get_principal(principal_id).status == "active"
            except IAMNotFoundError:
                return False

        active = await _as_api(status)
        self._active[principal_id] = (active, now)
        if len(self._active) > 10_000:
            self._active.clear()
        return active

    def forget(self, principal_id: str) -> None:
        self._active.pop(principal_id, None)


def default_identity() -> IIdentityService | None:
    services = engine_services()
    return services.identity if services is not None and services.identity_available() else None


def default_iam() -> Any | None:
    services = engine_services()
    return services.iam if services is not None and services.iam_available() else None
