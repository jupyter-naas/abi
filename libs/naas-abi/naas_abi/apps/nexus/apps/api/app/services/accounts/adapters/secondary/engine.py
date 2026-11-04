"""The engine's IAM and identity services, as the accounts' directory calls them.

* IAM's reads (who is who, the platform admins, the owners) are Nexus's own, as
  ``api`` for nobody, after the route let the caller list accounts;
* IAM's changes (suspend, resume, delete, what a principal holds) are made **as the
  caller** (``EngineIamGateway.bind``): IAM administration is never ``api``'s, so IAM
  decides them by the caller's own policies (``iam:SuspendPrincipal``, ...);
* the platform admin's role is attached through ``MEMBERSHIPS`` as ``api`` on behalf
  of the caller, as every role is;
* the identity provider is called as ``api`` on behalf of the caller, so IAM checks
  ``identity:*`` for both.

The services are blocking: each call runs in a worker thread.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any, TypeVar

from naas_abi.apps.nexus.apps.api.app.services.accounts.port import (
    AccessGateway,
    AccessRefused,
    Holdings,
    IdentityGateway,
    Principal,
    Provider,
    ProviderAccount,
    ProviderManaged,
    ProviderUnreachable,
)
from naas_abi.apps.nexus.apps.api.app.services.iam import runtime
from naas_abi.apps.nexus.apps.api.app.services.iam.authz import AUTHZ
from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import (
    MEMBERSHIPS,
    MembershipDenied,
    UnknownUserError,
    role_of_policy,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.names import is_org_container
from naas_abi.apps.nexus.apps.api.app.services.iam_admin.adapters.secondary.engine import (
    EngineIamGateway,
)
from naas_abi_core.engine.call_context import as_service_account, use_call_context
from naas_abi_core.services.iam.IAMPorts import (
    IAMConflictError,
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

_T = TypeVar("_T")
NEXUS_IDENTITY = "api"


async def _as_api(fn: Callable[[], _T], *, by: str | None = None) -> _T:
    """``fn`` as ``api``: for nobody, or (``by``) on behalf of that user."""
    context = AUTHZ.context(by) if by is not None else None

    def call() -> _T:
        if context is not None:
            with use_call_context(context):
                return fn()
        with as_service_account(NEXUS_IDENTITY):
            return fn()

    return await run_in_threadpool(call)


def _refused(exc: Exception) -> AccessRefused:
    return AccessRefused(getattr(exc, "message", None) or str(exc) or "Refused")


class EngineAccessGateway(AccessGateway):
    def __init__(self, gateway: EngineIamGateway | None = None) -> None:
        self._gateway = gateway or EngineIamGateway()

    async def _as_caller(self, by: str, work: Callable[[Any], _T]) -> _T:
        try:
            bound = self._gateway.bind(by)
        except PermissionDeniedError as exc:
            raise _refused(exc) from exc
        try:
            return await run_in_threadpool(work, bound)
        except PermissionDeniedError as exc:
            raise _refused(exc) from exc
        except (IAMNotFoundError, ResourceNotFoundError) as exc:
            # How IAM answers a caller who may not even see the principal.
            raise AccessRefused(f"IAM refused it: {exc}") from exc
        except IAMConflictError as exc:
            raise AccessRefused(str(exc)) from exc

    async def principals(self, user_ids: Sequence[str]) -> dict[str, Principal]:
        wanted = list(dict.fromkeys(user_ids))
        if not wanted:
            return {}

        def work() -> dict[str, Principal]:
            iam = runtime.iam()
            found: dict[str, Principal] = {}
            for user_id in wanted:
                try:
                    record = iam.resolve_user(user_id)
                except (IAMNotFoundError, ResourceNotFoundError):
                    record = None
                if record is not None and record.kind == "user":
                    found[user_id] = Principal(str(record.id), record.status)
            return found

        return await _as_api(work)

    async def principal(self, user_id: str) -> Principal:
        try:
            principal_id = await MEMBERSHIPS.principal_id(user_id)
        except UnknownUserError as exc:
            raise AccessRefused(str(exc)) from exc
        found = (await self.principals([user_id])).get(user_id)
        return found or Principal(principal_id, "active")

    async def platform_admins(self) -> set[str]:
        return await MEMBERSHIPS.platform_admins()

    async def set_platform_admin(self, user_id: str, on: bool, *, by: str) -> None:
        try:
            await MEMBERSHIPS.set_platform_admin(user_id, on, by=by)
        except (PermissionDeniedError, MembershipDenied) as exc:
            raise _refused(exc) from exc

    async def suspend(self, principal_id: str, *, by: str) -> None:
        await self._as_caller(by, lambda iam: iam.suspend_principal(principal_id))

    async def resume(self, principal_id: str, *, by: str) -> None:
        await self._as_caller(by, lambda iam: iam.resume_principal(principal_id))

    async def holdings(self, principal_id: str, *, by: str) -> Holdings:
        def work(iam: Any) -> Holdings:
            attachments = list(iam.list_attachments(principal_id=principal_id))
            groups = list(iam.list_principal_groups(principal_id))
            keys = [
                k for k in iam.list_keys(principal_id) if getattr(k, "revoked_at", None) is None
            ]
            roles = tuple(
                (str(a.scope), role)
                for a in attachments
                if a.scope is not None
                and not str(a.scope).endswith("/*")
                and (role := role_of_policy(a.policy_id)) is not None
            )
            return Holdings(
                attachments=len(attachments), groups=len(groups), api_keys=len(keys), roles=roles
            )

        return await self._as_caller(by, work)

    async def delete(self, principal_id: str, *, by: str) -> None:
        """Idempotent: a principal already deleted (an earlier attempt that failed
        after IAM's part) is left as it is."""

        def deleted() -> bool:
            try:
                return str(runtime.iam().get_principal(principal_id).status) == "deleted"
            except (IAMNotFoundError, ResourceNotFoundError):
                return False

        if await _as_api(deleted):
            return

        def work(iam: Any) -> None:
            # Every token issued for them stops, and their keys (personal ones too).
            iam.revoke_tokens(principal_id, include_keys=True)
            iam.delete_principal(principal_id)

        await self._as_caller(by, work)

    async def sole_owner_of(self, principal_id: str) -> list[str]:
        """The organizations whose only owner they are."""

        def work() -> list[str]:
            alone = []
            for scope, members in MEMBERSHIPS.members_by_scope(runtime.iam()).items():
                if not is_org_container(scope):
                    # A workspace keeps its organization's owners and admins (the
                    # platform admin for one in none): it is never left unadministered.
                    continue
                owners = [m.principal_id for m in members if m.role == "owner"]
                if owners == [principal_id]:
                    alone.append(scope)
            return sorted(alone)

        return await _as_api(work)


class EngineIdentityGateway(IdentityGateway):
    def __init__(self, identity: Callable[[], Any | None]) -> None:
        self._identity = identity

    def _service(self) -> Any:
        service = self._identity()
        if service is None:
            raise ProviderUnreachable("The engine's identity service is not loaded")
        return service

    async def _call(self, fn: Callable[[Any], _T], *, by: str) -> _T:
        service = self._service()
        try:
            return await _as_api(lambda: fn(service), by=by)
        except NotImplementedError as exc:
            raise ProviderManaged(str(exc)) from exc
        except (PermissionDeniedError, IAMNotFoundError, ResourceNotFoundError) as exc:
            raise _refused(exc) from exc
        except UnknownProviderError as exc:  # how a provider the caller may not see answers
            raise AccessRefused(str(exc)) from exc
        except (ProviderUnavailableError, ProvisioningError, ValueError) as exc:
            raise ProviderUnreachable(str(exc)) from exc

    async def providers(self) -> list[Provider]:
        service = self._identity()
        if service is None:
            return []
        try:
            found = await _as_api(service.list_providers)
        except ProviderUnavailableError:
            return []
        return [Provider(p.name, p.display_name, p.provisioning == "none") for p in found]

    async def find(self, provider: str, email: str, *, by: str) -> ProviderAccount | None:
        user = await self._call(lambda s: s.find_provisioned_user(provider, email), by=by)
        return _account(provider, user)

    async def update(
        self,
        provider: str,
        subject: str,
        *,
        name: str | None = None,
        disabled: bool | None = None,
        by: str,
    ) -> ProviderAccount | None:
        user = await self._call(
            lambda s: s.update_provisioned_user(provider, subject, name=name, disabled=disabled),
            by=by,
        )
        return _account(provider, user)

    async def delete(self, provider: str, subject: str, *, by: str) -> bool:
        return bool(await self._call(lambda s: s.delete_provisioned_user(provider, subject), by=by))


def _account(provider: str, user: Any) -> ProviderAccount | None:
    if user is None or not getattr(user, "subject", None):
        return None
    return ProviderAccount(
        provider=provider,
        subject=str(user.subject),
        name=getattr(user, "name", None),
        disabled=bool(getattr(user, "disabled", False)),
    )
