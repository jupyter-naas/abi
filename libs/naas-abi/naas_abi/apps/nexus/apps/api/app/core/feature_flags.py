from __future__ import annotations

from collections.abc import Mapping

from naas_abi.apps.nexus.apps.api.app.core.config import FeatureFlagsConfig

KNOWN_FEATURE_KEYS: tuple[str, ...] = (
    "maps",
    "chat",
    "files",
    "agents",
    "skills",
    "apps",
    "marketplace",
    "search",
    "ontology",
    "graph",
    "datasets",
    "settings",
    # In-app coding workspaces (IDE + git/review). Opt-in: off unless a
    # deployment adds "code" to enabled_features + role_baseline in
    # nexus_config.feature_flags. Never in the built-in defaults.
    "code",
    # Business slides (Forgejo decks + Monaco). On for workspace members by
    # default, like files; never shows Coder chrome.
    "slides",
)


def resolve_role_baseline(
    feature_flags_config: FeatureFlagsConfig,
    *,
    organization_id: str | None = None,
    organization_override: Mapping[str, list[str]] | None = None,
) -> dict[str, list[str]]:
    """Deployment role_baseline, overlaid by org config then an explicit override.

    Merge order (later wins):
    1. deployment ``role_baseline``
    2. optional YAML ``organization_overrides[organization_id]``
    3. durable DB overlay passed as ``organization_override``
    """
    baseline = {
        role: list(features)
        for role, features in feature_flags_config.role_baseline.items()
    }
    if organization_id:
        cfg_override = feature_flags_config.organization_overrides.get(organization_id)
        if cfg_override:
            for role, features in cfg_override.items():
                baseline[role] = list(features)
    if organization_override:
        for role, features in organization_override.items():
            baseline[role] = list(features)
    return baseline


def build_feature_flags(
    *,
    role: str,
    feature_flags_config: FeatureFlagsConfig,
    workspace_slug: str | None,
    workspace_id: str | None,
    organization_id: str | None = None,
    organization_override: Mapping[str, list[str]] | None = None,
) -> dict[str, bool]:
    """Build effective feature flags for a workspace user."""
    enabled_catalog = _resolve_enabled_catalog(feature_flags_config.enabled_features)
    role_baseline = resolve_role_baseline(
        feature_flags_config,
        organization_id=organization_id,
        organization_override=organization_override,
    )
    baseline = {
        key for key in role_baseline.get(role, []) if key in enabled_catalog
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
