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


def _default() -> IamAdminService:
    from naas_abi.apps.nexus.apps.api.app.core import database
    from naas_abi.apps.nexus.apps.api.app.services.feature_access.adapters.secondary.postgres import (  # noqa: E501
        SqlFeaturePolicyStore,
    )

    return IamAdminService(
        EngineIamGateway(),
        SqlAdminAuditLog(lambda: database.async_engine, prefix=AUDIT_PREFIX),
        managed_from=SqlFeaturePolicyStore(lambda: database.AsyncSessionLocal()).managed_among,
        org_access_of=_org_access_of,
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
