from __future__ import annotations

import json
from collections.abc import Collection, Iterable, Mapping

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
    # default; members and viewers get it through the org overlay or a policy
    # granting it (IAM decides: ``services/iam/catalog/tasks.py``).
    "tasks",
)

# Roles a workspace grants; a feature is "offered" when on for one of them.
BASELINE_ROLES: tuple[str, ...] = ("owner", "admin", "member", "viewer")

# Settings always stays reachable: a set never leaves it out (Nexus adds it to
# every feature set it records).
PINNED_FEATURES: tuple[str, ...] = ("settings",)


def with_pinned(features: Iterable[str] | None) -> list[str] | None:
    """A feature set with the features that always stay reachable; None stays None
    (every feature)."""
    if features is None:
        return None
    return sorted({*features, *PINNED_FEATURES})


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
        role: list(features) for role, features in feature_flags_config.role_baseline.items()
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
    workspace_slug: str | None = None,
    workspace_id: str | None = None,
    organization_id: str | None = None,
    organization_override: Mapping[str, list[str]] | None = None,
    feature_set: Collection[str] | None = None,
) -> dict[str, bool]:
    """The features a role has in a workspace by default: the role's defaults
    (deployment ``role_baseline``, the org overlays), within ``enabled_features``
    and within the workspace's ``feature_set`` (its set within its org's, IAM's:
    ``services/iam/sets.py``; None for every feature).

    What a user may use is IAM's ``nexus:UseFeature``, which also counts the
    policies granting features (``services/iam/sets.user_feature_flags``)."""
    enabled_catalog = _resolve_enabled_catalog(feature_flags_config.enabled_features)
    role_baseline = resolve_role_baseline(
        feature_flags_config,
        organization_id=organization_id,
        organization_override=organization_override,
    )
    allowed = (
        enabled_catalog
        if feature_set is None
        else enabled_catalog & {*feature_set, *PINNED_FEATURES}
    )
    baseline = {key for key in role_baseline.get(role, []) if key in allowed}
    return {key: (key in baseline) for key in KNOWN_FEATURE_KEYS}


def workspace_features(
    *,
    roles: tuple[str, ...],
    feature_flags_config: FeatureFlagsConfig,
    workspace_slug: str | None = None,
    workspace_id: str | None = None,
    organization_id: str | None = None,
    organization_override: Mapping[str, list[str]] | None = None,
    feature_set: Collection[str] | None = None,
) -> list[str]:
    """Features a workspace offers: on for at least one of ``roles``, in catalog order."""
    enabled: set[str] = set()
    for role in roles:
        flags = build_feature_flags(
            role=role,
            feature_flags_config=feature_flags_config,
            organization_id=organization_id,
            organization_override=organization_override,
            feature_set=feature_set,
        )
        enabled.update(key for key, on in flags.items() if on)
    return [key for key in KNOWN_FEATURE_KEYS if key in enabled]


def enabled_feature_catalog(feature_flags_config: FeatureFlagsConfig) -> list[str]:
    """Deployment catalog (``enabled_features``) in ``KNOWN_FEATURE_KEYS`` order."""
    catalog = _resolve_enabled_catalog(feature_flags_config.enabled_features)
    return [key for key in KNOWN_FEATURE_KEYS if key in catalog]


def parse_feature_overrides(raw: str | None) -> dict[str, bool] | None:
    """``workspaces.feature_overrides`` (JSON text) to a dict; ``None`` when unset.

    Read once, by the move of the overrides into the workspaces' feature sets
    (``services/iam/sets.migrate_feature_overrides``)."""
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


def feature_set_from_overrides(overrides: Mapping[str, bool] | None) -> list[str] | None:
    """The feature set per-workspace overrides stand for: every known feature
    but those turned off (a feature the deployment enables later included), and
    always the pinned ones; None when none is off (nothing narrows). The one rule
    of the start-up move (``services/iam/sets.py``) and the snapshot import."""
    off = {key for key, on in (overrides or {}).items() if not on}
    if not off:
        return None
    return [key for key in KNOWN_FEATURE_KEYS if key not in off or key in PINNED_FEATURES]


def _resolve_enabled_catalog(enabled_features: list[str]) -> set[str]:
    known = {key for key in enabled_features if key in KNOWN_FEATURE_KEYS}
    if known:
        return known
    return set(KNOWN_FEATURE_KEYS)
