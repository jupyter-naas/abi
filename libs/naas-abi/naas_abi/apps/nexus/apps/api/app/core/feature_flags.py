from __future__ import annotations

from collections.abc import Mapping

from naas_abi.apps.nexus.apps.api.app.core.config import FeatureFlagsConfig

KNOWN_FEATURE_KEYS: tuple[str, ...] = (
    "chat",
    "files",
    "agents",
    "knowledge",
    "settings",
)


def build_feature_flags(
    *,
    role: str,
    feature_flags_config: FeatureFlagsConfig,
    workspace_slug: str | None,
    workspace_id: str | None,
) -> dict[str, bool]:
    """Build effective feature flags for a workspace user."""
    enabled_catalog = _resolve_enabled_catalog(feature_flags_config.enabled_features)
    baseline = {
        key for key in feature_flags_config.role_baseline.get(role, []) if key in enabled_catalog
    }
    flags: dict[str, bool] = {key: (key in baseline) for key in KNOWN_FEATURE_KEYS}

    overrides = _resolve_workspace_overrides(
        workspace_overrides=feature_flags_config.workspace_overrides,
        workspace_slug=workspace_slug,
        workspace_id=workspace_id,
    )
    for key, value in overrides.items():
        if key in enabled_catalog:
            flags[key] = bool(value)

    for key in KNOWN_FEATURE_KEYS:
        if key not in enabled_catalog:
            flags[key] = False

    return flags


def _resolve_enabled_catalog(enabled_features: list[str]) -> set[str]:
    known = {key for key in enabled_features if key in KNOWN_FEATURE_KEYS}
    if known:
        return known
    return set(KNOWN_FEATURE_KEYS)


def _resolve_workspace_overrides(
    *,
    workspace_overrides: Mapping[str, Mapping[str, bool]],
    workspace_slug: str | None,
    workspace_id: str | None,
) -> Mapping[str, bool]:
    if workspace_slug and workspace_slug in workspace_overrides:
        return workspace_overrides[workspace_slug]
    if workspace_id and workspace_id in workspace_overrides:
        return workspace_overrides[workspace_id]
    return {}
