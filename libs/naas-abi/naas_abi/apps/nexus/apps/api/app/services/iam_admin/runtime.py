"""Build the IAM admin service from the engine's IAM and Nexus's audit log; tests
replace it with ``configure``."""

from __future__ import annotations

from collections.abc import Callable

from naas_abi.apps.nexus.apps.api.app.services.iam_admin.adapters.secondary.engine import (
    EngineIamGateway,
)
from naas_abi.apps.nexus.apps.api.app.services.iam_admin.service import IamAdminService
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.sql_audit_log import (
    SqlAdminAuditLog,
)

# IAM's changes are kept in Nexus's ``audit_logs`` table under this action prefix.
AUDIT_PREFIX = "iam."

Provider = Callable[[], IamAdminService]


async def _follow_member(principal_id: str) -> None:
    """Platform Files follows the person's workspace groups (#1590), as ``api``."""
    from naas_abi.apps.nexus.apps.api.app.services.iam import platform_files
    from naas_abi.apps.nexus.apps.api.app.services.iam import runtime as iam_runtime
    from naas_abi_core.engine.call_context import as_service_account
    from starlette.concurrency import run_in_threadpool

    def work() -> None:
        with as_service_account("api"):
            platform_files.follow(iam_runtime.iam(), principal_id)

    await run_in_threadpool(work)


async def follow_group(group_id: str) -> None:
    """Its members belong, through the group, to its membership container ("<W> workspace")
    and to each container it holds a role at: what follows who belongs there (shared
    graphs, ``MEMBERSHIPS.changed``) follows, as when Nexus moves a person. Read as ``api``:
    an attachment the caller may not list still gives a place."""
    from naas_abi.apps.nexus.apps.api.app.services.iam import runtime as iam_runtime
    from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import MEMBERSHIPS
    from naas_abi_core.engine.call_context import as_service_account
    from starlette.concurrency import run_in_threadpool

    def places() -> list[str]:
        iam = iam_runtime.iam()
        with as_service_account("api"):
            group = iam.get_group(group_id)
            found = {a.scope for a in iam.list_attachments(principal_id=group_id) if a.scope}
        membership_of = getattr(group, "membership_of", None)
        if membership_of:
            found.add(membership_of)
        return sorted(found)

    for scope in await run_in_threadpool(places):
        await MEMBERSHIPS.changed(scope)


def _default() -> IamAdminService:
    from naas_abi.apps.nexus.apps.api.app.core import database
    from naas_abi.apps.nexus.apps.api.app.services.feature_access.adapters.secondary.postgres import (  # noqa: E501
        SqlFeaturePolicyStore,
    )
    from naas_abi.apps.nexus.apps.api.app.services.iam_admin.adapters.secondary.nexus_accounts import (  # noqa: E501
        SqlAccountNames,
    )

    return IamAdminService(
        EngineIamGateway(),
        SqlAdminAuditLog(lambda: database.async_engine, prefix=AUDIT_PREFIX),
        managed_from=SqlFeaturePolicyStore(lambda: database.AsyncSessionLocal()).managed_among,
        org_access_of=_org_access_of,
        follow_member=_follow_member,
        account_names=SqlAccountNames(lambda: database.AsyncSessionLocal()).names_of,
        follow_group=follow_group,
    )


async def _org_access_of(org_id: str) -> str | None:
    """ "<O> access", as ``container_defaults`` recorded it for the organization."""
    from naas_abi.apps.nexus.apps.api.app.services.iam.container_defaults import (
        CONTAINER_DEFAULTS,
    )
    from naas_abi.apps.nexus.apps.api.app.services.iam.names import org_container

    record = await CONTAINER_DEFAULTS.record_of(org_container(org_id))
    return record.access_policy_id if record is not None else None


_provider: Provider = _default
_cached: IamAdminService | None = None


def configure(provider: Provider | None) -> Provider:
    """Replace the service (tests); ``None`` restores the engine's. Returns the previous one."""
    global _provider, _cached
    previous = _provider
    _provider = provider if provider is not None else _default
    _cached = None
    return previous


def get_iam_admin_service() -> IamAdminService:
    global _cached
    if _cached is None:
        _cached = _provider()
    return _cached
