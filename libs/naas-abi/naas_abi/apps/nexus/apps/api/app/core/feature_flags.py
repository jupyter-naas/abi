"""The deployment's features: which exist (``enabled_features``) and which a
workspace offers (those within its set).

Who may use one is IAM's ``nexus:UseFeature``, granted by policies only: no role
brings a feature. A feature outside ``enabled_features`` exists nowhere: it is
offered nowhere and usable by nobody, the platform admin included
(``services/iam/authz.py``)."""

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
    # deployment adds "code" to enabled_features in nexus_config.feature_flags.
    "code",
    # Business slides (Forgejo decks + Monaco); never shows Coder chrome.
    "slides",
    # Business documents (Forgejo HTML + Monaco).
    "documents",
    # Business sheets (Forgejo HTML workbook + XLSX export).
    "sheets",
    # Workspace tasks (weekly iterations, board view).
    "tasks",
)

# Settings always stays reachable: a set never leaves it out (Nexus adds it to
# every feature set it records).
PINNED_FEATURES: tuple[str, ...] = ("settings",)


def with_pinned(features: Iterable[str] | None) -> list[str] | None:
    """A feature set with the features that always stay reachable; None stays None
    (every feature)."""
    if features is None:
        return None
    return sorted({*features, *PINNED_FEATURES})


def offered_features(
    feature_flags_config: FeatureFlagsConfig, feature_set: Collection[str] | None = None
) -> list[str]:
    """The features a workspace offers, in catalog order: the deployment's enabled
    ones within the workspace's ``feature_set`` (its set within its org's, IAM's:
    ``services/iam/sets.py``; None for every feature), the pinned ones always.
    Who uses one is a policy's: ``services/iam/sets.user_feature_flags``."""
    catalog = enabled_feature_catalog(feature_flags_config)
    if feature_set is None:
        return catalog
    kept = {*feature_set, *PINNED_FEATURES}
    return [key for key in catalog if key in kept]


def feature_enabled(feature_flags_config: FeatureFlagsConfig, key: str) -> bool:
    """Whether ``key`` exists in this deployment (``enabled_features``)."""
    return key in _resolve_enabled_catalog(feature_flags_config.enabled_features)


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
