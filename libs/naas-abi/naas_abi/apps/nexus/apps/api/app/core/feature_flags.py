from __future__ import annotations

import json
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
    # Business documents (Forgejo HTML + Monaco). Same default grant as slides.
    "documents",
    # Business sheets (Forgejo HTML workbook + XLSX export). Same default as slides.
    "sheets",
    # Workspace tasks (weekly iterations, board view). Owners and admins only by
    # default; members and viewers get it through an org or workspace override.
    "tasks",
)

# Roles a workspace grants; a feature is "offered" when on for one of them.
BASELINE_ROLES: tuple[str, ...] = ("owner", "admin", "member", "viewer")

# Settings always stays reachable, so it cannot be overridden per workspace.
PINNED_FEATURES: tuple[str, ...] = ("settings",)


class InvalidFeatureOverridesError(ValueError):
    """Workspace feature overrides outside the catalog or on a pinned feature."""


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
    workspace_override: Mapping[str, bool] | None = None,
) -> dict[str, bool]:
    """Build effective feature flags for a workspace user.

    ``workspace_override`` is the durable overlay saved from Organization
    Settings > Workspaces (``workspaces.feature_overrides``). When it is set
    (even empty) it replaces the YAML ``workspace_overrides`` entry for this
    workspace: the config only bootstraps it.
    """
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

    overrides = (
        workspace_override
        if workspace_override is not None
        else _resolve_workspace_overrides(
            workspace_overrides=feature_flags_config.workspace_overrides,
            workspace_slug=workspace_slug,
            workspace_id=workspace_id,
        )
    )
    for key, value in overrides.items():
        if key in enabled_catalog:
            flags[key] = bool(value)

    for key in KNOWN_FEATURE_KEYS:
        if key not in enabled_catalog:
            flags[key] = False

    return flags


def effective_workspace_overrides(
    feature_flags_config: FeatureFlagsConfig,
    *,
    workspace_slug: str | None,
    workspace_id: str | None,
    workspace_override: Mapping[str, bool] | None,
) -> tuple[dict[str, bool], str | None]:
    """The overrides that apply to a workspace and where they come from.

    Returns ``(overrides, source)`` with source ``"database"`` (saved in the
    app), ``"deployment"`` (YAML ``workspace_overrides``) or ``None``.
    """
    if workspace_override is not None:
        return dict(workspace_override), "database"
    configured = _resolve_workspace_overrides(
        workspace_overrides=feature_flags_config.workspace_overrides,
        workspace_slug=workspace_slug,
        workspace_id=workspace_id,
    )
    if configured:
        return {key: bool(value) for key, value in configured.items()}, "deployment"
    return {}, None


def workspace_features(
    *,
    roles: tuple[str, ...],
    feature_flags_config: FeatureFlagsConfig,
    workspace_slug: str | None,
    workspace_id: str | None,
    organization_id: str | None = None,
    organization_override: Mapping[str, list[str]] | None = None,
    workspace_override: Mapping[str, bool] | None = None,
) -> list[str]:
    """Features a workspace offers: on for at least one of ``roles``, in catalog order."""
    enabled: set[str] = set()
    for role in roles:
        flags = build_feature_flags(
            role=role,
            feature_flags_config=feature_flags_config,
            workspace_slug=workspace_slug,
            workspace_id=workspace_id,
            organization_id=organization_id,
            organization_override=organization_override,
            workspace_override=workspace_override,
        )
        enabled.update(key for key, on in flags.items() if on)
    return [key for key in KNOWN_FEATURE_KEYS if key in enabled]


def enabled_feature_catalog(feature_flags_config: FeatureFlagsConfig) -> list[str]:
    """Deployment catalog (``enabled_features``) in ``KNOWN_FEATURE_KEYS`` order."""
    catalog = _resolve_enabled_catalog(feature_flags_config.enabled_features)
    return [key for key in KNOWN_FEATURE_KEYS if key in catalog]


def validate_workspace_feature_overrides(
    feature_flags_config: FeatureFlagsConfig, overrides: Mapping[str, bool]
) -> dict[str, bool]:
    """Check per-workspace overrides against the deployment catalog and pins.

    Raises ``InvalidFeatureOverridesError`` naming the offending features.
    """
    catalog = set(enabled_feature_catalog(feature_flags_config))
    outside = sorted(key for key in overrides if key not in catalog)
    if outside:
        raise InvalidFeatureOverridesError(
            f"Features not enabled in deployment catalog: {', '.join(outside)}"
        )
    pinned = sorted(key for key in overrides if key in PINNED_FEATURES)
    if pinned:
        raise InvalidFeatureOverridesError(f"Features always on: {', '.join(pinned)}")
    return {str(key): bool(value) for key, value in overrides.items()}


def parse_feature_overrides(raw: str | None) -> dict[str, bool] | None:
    """``workspaces.feature_overrides`` (JSON text) to a dict; ``None`` when unset."""
    if raw is None:
        return None
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    return {
        str(key): bool(value)
        for key, value in data.items()
        if key in KNOWN_FEATURE_KEYS and isinstance(value, bool)
    }


def dump_feature_overrides(overrides: Mapping[str, bool] | None) -> str | None:
    if overrides is None:
        return None
    return json.dumps({key: bool(overrides[key]) for key in sorted(overrides)})


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
