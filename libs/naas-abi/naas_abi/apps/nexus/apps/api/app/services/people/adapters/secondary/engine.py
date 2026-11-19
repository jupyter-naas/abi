"""The engine's identity service and IAM, as the people service calls them.

What gives access (a pending grant, a role, a policy) is written as ``api`` on
behalf of the inviting person, so IAM checks that they may attach it and hold what
it grants; the provider's admin API, the principals and the take-backs are Nexus's
own (``api`` for nobody), made only under the warrant the service checked first.
IAM's refusals become ``GrantNotHeldError``; the provider's failures
``ProvisioningFailedError``. The services are blocking: each call runs in a worker
thread.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any, TypeVar

from naas_abi.apps.nexus.apps.api.app.services.iam.authz import AUTHZ
from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import (
    MEMBERSHIPS,
    MembershipDenied,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.names import org_container
from naas_abi.apps.nexus.apps.api.app.services.people.port import (
    AccessGateway,
    Grant,
    GrantNotHeldError,
    IdentityGateway,
    ProviderInfo,
    Provisioned,
    ProvisioningFailedError,
    ProvisioningRefused,
    RetiredIdentityError,
    Warrant,
)
from naas_abi_core import logger
from naas_abi_core.engine.call_context import as_service_account, use_call_context
from naas_abi_core.services.iam.IAMPorts import (
    IAMNotFoundError,
    PermissionDeniedError,
    ResourceNotFoundError,
)
from naas_abi_core.services.identity.IdentityPorts import (
    ProviderUnavailableError,
    ProvisioningError,
    UnknownProviderError,
)
from starlette.concurrency import run_in_threadpool

NEXUS_IDENTITY = "api"
_T = TypeVar("_T")


async def _as_api(fn: Callable[[], _T], *, by: str | None = None) -> _T:
    """Run ``fn`` as ``api``: for nobody, or on behalf of ``by``."""
    context = AUTHZ.context(by) if by is not None else None

    def call() -> _T:
        if context is not None:
            with use_call_context(context):
                return fn()
        with as_service_account(NEXUS_IDENTITY):
            return fn()

    return await run_in_threadpool(call)


def _refused(exc: Exception) -> GrantNotHeldError:
    return GrantNotHeldError(str(exc) or "You may not give this access here")


class EngineIdentityGateway(IdentityGateway):
    def __init__(self, identity: Callable[[], Any | None]) -> None:
        self._identity = identity

    def _service(self) -> Any:
        service = self._identity()
        if service is None:
            raise ProvisioningFailedError("The engine's identity service is not loaded")
        return service

    async def providers(self) -> tuple[list[ProviderInfo], str | None]:
        service = self._identity()
        if service is None:
            return [], None
        try:
            found, default = await _as_api(
                lambda: (service.list_providers(), service.default_provider)
            )
        except ProviderUnavailableError:
            return [], None
        return [
            ProviderInfo(p.name, p.display_name, p.issuer, p.provisioning) for p in found
        ], default

    async def provision(
        self, provider: ProviderInfo, email: str, name: str | None, *, by: str | None = None
    ) -> Provisioned | None:
        if provider.managed_in_provider:
            return None
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
            UnknownProviderError,
        ) as exc:
            if by is not None:
                raise ProvisioningRefused(str(exc)) from exc
            # Nexus itself may not (a deployment withholding the right).
            raise ProvisioningFailedError(str(exc)) from exc
        except (ProviderUnavailableError, ProvisioningError) as exc:
            raise ProvisioningFailedError(str(exc)) from exc
        return Provisioned(
            subject=getattr(user, "subject", None),
            created=bool(getattr(user, "created", False)),
            warning=getattr(user, "warning", None),
        )

    async def delete(self, provider: str, subject: str) -> None:
        service = self._service()
        await _as_api(lambda: service.delete_provisioned_user(provider, subject))


class EngineAccessGateway(AccessGateway):
    def __init__(self, iam: Callable[[], Any | None]) -> None:
        self._iam = iam

    def _service(self) -> Any:
        service = self._iam()
        if service is None:
            raise ProvisioningFailedError("The engine's IAM service is not loaded")
        return service

    async def scope(self, grant: Grant) -> str:
        if grant.scope == "organization":
            return org_container(grant.scope_id)
        container = await AUTHZ.container_of(grant.scope_id)
        if container is None:
            raise LookupError(grant.scope_id)
        return container

    async def warrant(
        self, provider: str, email: str, grants: Sequence[tuple[str, str]], *, by: str
    ) -> Warrant:
        iam = self._service()
        ids: list[str] = []
        made: list[str] = []
        try:
            for policy_id, scope in grants:
                # The whole truth (as Nexus): a grant an older invitation holds is
                # not this call's to withdraw.
                held = await _as_api(
                    lambda p=policy_id, s=scope: any(  # type: ignore[misc]
                        g.scope == s
                        for g in iam.list_pending_grants(
                            provider=provider, email=email, policy_id=p
                        )
                    )
                )
                grant = await _as_api(
                    lambda p=policy_id, s=scope: iam.create_pending_grant(provider, email, p, s),  # type: ignore[misc]
                    by=by,
                )
                ids.append(str(grant.id))
                if not held:
                    made.append(str(grant.id))
        except (PermissionDeniedError, IAMNotFoundError, ResourceNotFoundError) as exc:
            await self.withdraw(made)
            raise _refused(exc) from exc
        except Exception:
            await self.withdraw(made)
            raise
        return Warrant(grant_ids=tuple(ids), made=tuple(made))

    async def withdraw(self, grant_ids: Sequence[str]) -> None:
        iam = self._service()
        for grant_id in grant_ids:
            try:
                await _as_api(lambda g=grant_id: iam.revoke_pending_grant(g))  # type: ignore[misc]
            except Exception as exc:  # noqa: BLE001 - a grant already gone is gone
                logger.warning(f"Could not revoke pending grant {grant_id}: {exc}")

    async def ensure_principal(
        self, issuer: str, subject: str, *, provider: str, email: str, name: str | None
    ) -> str:
        iam = self._service()
        record = await _as_api(
            lambda: iam.ensure_user(
                issuer, subject, provider=provider, email=email, display_name=name
            )
        )
        if str(record.status) != "active":
            raise RetiredIdentityError(
                f"The account of {email} at {provider} belongs to a "
                f"{record.status} user: it is not invited again"
            )
        return str(record.id)

    async def discard_principal(self, principal_id: str) -> None:
        iam = self._service()
        try:
            await _as_api(lambda: iam.delete_principal(principal_id))
        except Exception as exc:  # noqa: BLE001 - its identity is gone: it holds nothing
            logger.info(
                f"The principal {principal_id} of a failed invitation stays, holding nothing "
                f"(its account at the provider is deleted): {exc}"
            )

    async def roles_of(self, user_id: str) -> dict[str, str]:
        return await MEMBERSHIPS.roles_of(user_id)

    async def grant_role(self, user_id: str, role: str, scope: str, *, by: str) -> None:
        try:
            await MEMBERSHIPS.grant(user_id, role, scope, by=by)
        except (MembershipDenied, PermissionDeniedError, ResourceNotFoundError) as exc:
            raise _refused(exc) from exc

    async def revoke_role(self, user_id: str, scope: str) -> None:
        await MEMBERSHIPS.revoke(user_id, scope)

    async def attach(self, user_id: str, policy_id: str, scope: str, *, by: str) -> bool:
        iam = self._service()
        principal_id = await MEMBERSHIPS.principal_id(user_id)
        held = await _as_api(
            lambda: any(
                a.scope == scope
                for a in iam.list_attachments(principal_id=principal_id, policy_id=policy_id)
            )
        )
        try:
            await _as_api(lambda: iam.attach_policy(policy_id, principal_id, scope), by=by)
        except (PermissionDeniedError, IAMNotFoundError, ResourceNotFoundError) as exc:
            raise _refused(exc) from exc
        return not held

    async def detach(self, user_id: str, policy_id: str, scope: str) -> None:
        iam = self._service()
        principal_id = await MEMBERSHIPS.principal_id(user_id)
        await _as_api(lambda: iam.detach_policy(policy_id, principal_id, scope))
