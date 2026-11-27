"""The deployment's features: which the platform offers (``deployment_catalog``) and
which a workspace offers (those within its set).

Who may use one is IAM's ``nexus:UseFeature``, granted by policies only: no role
brings a feature. Every feature of ``KNOWN_FEATURE_KEYS`` is listed at the platform
(Platform settings › Access › Features); what the platform offers its organizations is
"Platform access" (``services/iam/platform_offer.py``), made from ``enabled_features``,
which decide alone while it does not exist. A feature the platform does not offer is
offered nowhere and usable by nobody, the platform admin included
(``services/iam/authz.py``)."""

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

# Settings always stayed reachable: the workspace feature sets an override made
# kept it (``feature_set_from_overrides``).
PINNED_FEATURES: tuple[str, ...] = ("settings",)


def deployment_catalog(feature_flags_config: FeatureFlagsConfig) -> list[str]:
    """The features the platform offers, in ``KNOWN_FEATURE_KEYS`` order: "Platform
    access" (``platform_offer``), else the deployment's ``enabled_features``. The pinned
    ones (Settings) follow ``enabled_features``: no offer switches them."""
    from naas_abi.apps.nexus.apps.api.app.services.iam import platform_offer

    configured = enabled_feature_catalog(feature_flags_config)
    platform = platform_offer.offered()
    if platform is None:
        return configured
    return [
        key
        for key in KNOWN_FEATURE_KEYS
        if key in platform or (key in PINNED_FEATURES and key in configured)
    ]


def offered_features(feature_flags_config: FeatureFlagsConfig) -> list[str]:
    """The features a workspace offers, in catalog order: those the platform offers.
    Who uses one is a policy's: ``services/iam/user_features``."""
    return deployment_catalog(feature_flags_config)


def offer_choices(feature_flags_config: FeatureFlagsConfig) -> list[str]:
    """The features an offer switches (General › Features, a policy's Configuration): the
    deployment's enabled ones but the pinned, which whoever administers the workspace keeps
    whatever the offer says (``user_features.ALWAYS_SHOWN``)."""
    return [key for key in deployment_catalog(feature_flags_config) if key not in PINNED_FEATURES]


def feature_enabled(feature_flags_config: FeatureFlagsConfig, key: str) -> bool:
    """Whether the platform offers ``key`` (``deployment_catalog``)."""
    return key in deployment_catalog(feature_flags_config)


def enabled_feature_catalog(feature_flags_config: FeatureFlagsConfig) -> list[str]:
    """Deployment catalog (``enabled_features``) in ``KNOWN_FEATURE_KEYS`` order."""
    catalog = _resolve_enabled_catalog(feature_flags_config.enabled_features)
    return [key for key in KNOWN_FEATURE_KEYS if key in catalog]


def parse_feature_overrides(raw: str | None) -> dict[str, bool] | None:
    """``workspaces.feature_overrides`` (JSON text) to a dict; ``None`` when unset.

    Read once, by the move of the overrides (``services/iam/feature_overrides``)."""
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
    always the pinned ones; None when none is off (nothing narrows). The rule of
    the start-up move (``services/iam/feature_overrides``)."""
    off = {key for key, on in (overrides or {}).items() if not on}
    if not off:
        return None
    return [key for key in KNOWN_FEATURE_KEYS if key not in off or key in PINNED_FEATURES]


def _resolve_enabled_catalog(enabled_features: list[str]) -> set[str]:
    known = {key for key in enabled_features if key in KNOWN_FEATURE_KEYS}
    if known:
        return known
    return set(KNOWN_FEATURE_KEYS)
