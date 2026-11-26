"""Build the feature access service from the engine's IAM, Nexus's database and its
audit log; tests replace it with ``configure``."""

from __future__ import annotations

from collections.abc import Callable

from naas_abi.apps.nexus.apps.api.app.services.feature_access.service import (
    FeatureAccessService,
)

Provider = Callable[[], FeatureAccessService]


def _features() -> list[str]:
    """What an offer switches: Settings is never one (``offer_choices``)."""
    from naas_abi.apps.nexus.apps.api.app.core.feature_flags import offer_choices
    from naas_abi.apps.nexus.apps.api.app.core.workspace_catalog_seed import live_settings

    return offer_choices(live_settings().feature_flags)


def _default() -> FeatureAccessService:
    from naas_abi.apps.nexus.apps.api.app.core import database
    from naas_abi.apps.nexus.apps.api.app.services.feature_access.adapters.secondary.postgres import (  # noqa: E501
        SqlFeaturePolicyStore,
    )
    from naas_abi.apps.nexus.apps.api.app.services.iam.authz import AUTHZ
    from naas_abi.apps.nexus.apps.api.app.services.iam.container_defaults import (
        CONTAINER_DEFAULTS,
    )
    from naas_abi.apps.nexus.apps.api.app.services.iam_admin.adapters.secondary.engine import (
        EngineIamGateway,
    )
    from naas_abi.apps.nexus.apps.api.app.services.iam_admin.runtime import AUDIT_PREFIX
    from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.sql_audit_log import (  # noqa: E501
        SqlAdminAuditLog,
    )

    return FeatureAccessService(
        EngineIamGateway(),
        SqlFeaturePolicyStore(lambda: database.AsyncSessionLocal()),
        SqlAdminAuditLog(lambda: database.async_engine, prefix=AUDIT_PREFIX),
        container_of=AUTHZ.container_of,
        defaults_of=CONTAINER_DEFAULTS.record_of,
        features=_features,
    )


_provider: Provider = _default
_cached: FeatureAccessService | None = None


def configure(provider: Provider | None) -> Provider:
    """Replace the service (tests); ``None`` restores the engine's. Returns the previous one."""
    global _provider, _cached
    previous = _provider
    _provider = provider if provider is not None else _default
    _cached = None
    return previous


def get_feature_access_service() -> FeatureAccessService:
    global _cached
    if _cached is None:
        _cached = _provider()
    return _cached
