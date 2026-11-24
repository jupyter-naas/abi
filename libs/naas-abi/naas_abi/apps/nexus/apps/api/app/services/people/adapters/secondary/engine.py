"""The engine's identity service and IAM, as the people service calls them.

What gives access (a group membership, the level) is checked as the inviting
person, by IAM's member change on each group and its level-group rule, then
written as ``api`` (``Memberships``: the seats, #1589), which records who asked;
the provider's admin API, the principals and the take-backs are Nexus's own
(``api`` for nobody), made only under the check the service ran first. IAM's
refusals become ``GrantNotHeldError``; the provider's failures
``ProvisioningFailedError``. The services are blocking: each call runs in a worker
thread.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any, Literal, TypeVar

from naas_abi.apps.nexus.apps.api.app.services.iam.authz import AUTHZ
from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import (
    MEMBERSHIPS,
    MembershipDenied,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.names import org_container
from naas_abi.apps.nexus.apps.api.app.services.people.port import (
    AccessGateway,
    GrantNotHeldError,
    IdentityGateway,
    Level,
    ProviderInfo,
    Provisioned,
    ProvisioningFailedError,
    ProvisioningRefused,
    RetiredIdentityError,
    Seat,
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


_DENIED = (MembershipDenied, PermissionDeniedError, ResourceNotFoundError, IAMNotFoundError)


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

    async def container(self, kind: Literal["organization", "workspace"], id: str) -> str:
        if kind == "organization":
            return org_container(id)
        container = await AUTHZ.container_of(id)
        if container is None:
            raise LookupError(id)
        return container

    async def check(
        self,
        user_id: str | None,
        seats: Sequence[Seat],
        *,
        level: Level | None,
        by: str,
        organization_id: str | None,
    ) -> None:
        try:
            await MEMBERSHIPS.check_seats(
                user_id, seats, level=level, by=by, org_id=organization_id
            )
        except _DENIED as exc:
            raise _refused(exc) from exc

    async def held(self, user_id: str, seats: Sequence[Seat]) -> set[Seat]:
        return await MEMBERSHIPS.held_seats(user_id, seats)

    async def level_of(self, user_id: str) -> Level | None:
        level = await MEMBERSHIPS.level_of(user_id)
        return level if level in ("viewer", "member") else None  # type: ignore[return-value]

    async def join(self, user_id: str, seat: Seat, *, by: str | None, level: Level | None) -> bool:
        try:
            return await MEMBERSHIPS.take_seat(user_id, seat, by=by, level=level)
        except _DENIED as exc:
            raise _refused(exc) from exc

    async def leave(self, user_id: str, seat: Seat, *, by: str | None) -> bool:
        try:
            return await MEMBERSHIPS.leave_seat(user_id, seat, by=by)
        except _DENIED as exc:
            raise _refused(exc) from exc

    async def check_leaving(self, user_id: str, seats: Sequence[Seat], *, by: str) -> None:
        try:
            await MEMBERSHIPS.check_leaving(user_id, seats, by=by)
        except _DENIED as exc:
            raise _refused(exc) from exc

    async def set_level(
        self, user_id: str, level: Level, *, by: str | None, where: Sequence[str] = ()
    ) -> Level | None:
        try:
            before = await MEMBERSHIPS.set_level(user_id, level, by=by, where=where)
        except _DENIED as exc:
            raise _refused(exc) from exc
        return before if before in ("viewer", "member") else None  # type: ignore[return-value]

    async def clear_level(self, user_id: str) -> None:
        await MEMBERSHIPS.clear_level(user_id)

    async def capability_groups(self, organization_id: str | None) -> list[tuple[str, str]]:
        return [
            (str(g.id), str(g.name)) for g in await MEMBERSHIPS.capability_groups(organization_id)
        ]

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
