"""The engine's identity and IAM services, as Nexus calls them for invitations.

Nexus decided whether the inviting person may invite (the route did). What gives
access (a pending grant, an IdP group binding) is written as ``api`` on behalf of
that person, so IAM also checks that they hold what it grants ("Grant only what
you hold"); reads and withdrawals are Nexus's own, ``api`` acting for nobody. The
services are blocking: each call runs in a worker thread.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any, TypeVar

from naas_abi.apps.nexus.apps.api.app.services.iam.authz import AUTHZ
from naas_abi.apps.nexus.apps.api.app.services.invites.port import (
    Directory,
    DirectoryGateway,
    GrantMade,
    GrantsGateway,
    IdpBindingView,
    ProviderChoice,
    Provisioned,
    ProvisioningRefused,
)
from naas_abi_core.engine.call_context import as_service_account, use_call_context
from naas_abi_core.services.iam.IAMPorts import (
    IAMNotFoundError,
    PermissionDeniedError,
    ResourceNotFoundError,
)
from naas_abi_core.services.identity.IdentityPorts import (
    ProviderUnavailableError,
    UnknownProviderError,
)
from starlette.concurrency import run_in_threadpool

NEXUS_IDENTITY = "api"
BUILTIN_PREFIX = "builtin."
_T = TypeVar("_T")


async def _as_api(fn: Callable[[], _T], *, by: str | None = None) -> _T:
    """Run ``fn`` as ``api``: for nobody, or (``by``) on behalf of that user, so IAM
    asks both: what Nexus may and what the user may."""
    context = AUTHZ.context(by) if by is not None else None

    def call() -> _T:
        if context is not None:
            with use_call_context(context):
                return fn()
        with as_service_account(NEXUS_IDENTITY):
            return fn()

    return await run_in_threadpool(call)


class EngineDirectoryGateway(DirectoryGateway):
    def __init__(self, identity: Callable[[], Any | None]) -> None:
        self._identity = identity

    def _service(self) -> Any:
        service = self._identity()
        if service is None:
            raise ProviderUnavailableError("The engine's identity service is not loaded")
        return service

    async def directory(self) -> Directory:
        service = self._identity()
        if service is None:
            return Directory()
        try:
            providers, default = await _as_api(
                lambda: (service.list_providers(), service.default_provider)
            )
        except ProviderUnavailableError:
            return Directory()
        return Directory(
            providers=tuple(
                ProviderChoice(p.name, p.display_name, p.provisioning) for p in providers
            ),
            default=default,
        )

    async def provision(
        self, provider: ProviderChoice, email: str, name: str | None, *, by: str | None = None
    ) -> Provisioned | None:
        if provider.managed_in_provider:
            return None  # its people are made in the provider: no call to make
        service = self._service()
        try:
            user = await _as_api(
                lambda: service.provision_user(provider.name, email, name=name), by=by
            )
        except NotImplementedError:
            return None
        except (
            PermissionDeniedError,
            IAMNotFoundError,
            ResourceNotFoundError,
            UnknownProviderError,  # how a provider the user may not see answers
        ) as exc:
            raise ProvisioningRefused(str(exc)) from exc
        return Provisioned(
            subject=user.subject, created=user.created, warning=getattr(user, "warning", None)
        )


class EngineGrantsGateway(GrantsGateway):
    def __init__(self, iam: Callable[[], Any | None]) -> None:
        self._iam = iam

    def _service(self) -> Any:
        service = self._iam()
        if service is None:
            raise ProviderUnavailableError("The engine's IAM service is not loaded")
        return service

    async def grant(
        self,
        provider: str,
        email: str,
        policy_id: str,
        scope: str | None,
        *,
        by: str | None = None,
    ) -> GrantMade:
        iam = self._service()
        # The whole truth, not what the inviting person may list: a grant another
        # invitation made is not this call's to take back.
        held = await _as_api(
            lambda: next(
                (
                    g
                    for g in iam.list_pending_grants(
                        provider=provider, email=email, policy_id=policy_id
                    )
                    if g.scope == scope
                ),
                None,
            )
        )
        grant = await _as_api(
            lambda: iam.create_pending_grant(provider, email, policy_id, scope), by=by
        )
        return GrantMade(id=str(grant.id), created=held is None)

    async def revoke(self, grant_id: str) -> None:
        iam = self._service()
        await _as_api(lambda: iam.revoke_pending_grant(grant_id))

    async def bind(
        self,
        provider: str,
        claim_value: str,
        policy_id: str,
        scope: str | None,
        *,
        by: str | None = None,
    ) -> None:
        iam = self._service()
        await _as_api(lambda: iam.bind_idp_group(provider, claim_value, policy_id, scope), by=by)

    async def unbind(
        self, provider: str, claim_value: str, policy_id: str, scope: str | None
    ) -> bool:
        iam = self._service()
        return bool(
            await _as_api(lambda: iam.unbind_idp_group(provider, claim_value, policy_id, scope))
        )

    async def bindings(self, scopes: Sequence[str]) -> list[IdpBindingView]:
        iam = self._service()
        wanted = set(scopes)
        found = await _as_api(lambda: iam.list_idp_bindings())
        return [
            IdpBindingView(
                provider=b.provider,
                claim_value=b.claim_value,
                role=b.policy_id.removeprefix(BUILTIN_PREFIX),
                scope=b.scope,
                group_id=b.group_id,
            )
            for b in found
            if b.scope in wanted and b.policy_id.startswith(BUILTIN_PREFIX)
        ]
