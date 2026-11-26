"""What the feature access service offers to switch: the deployment's features but the
pinned ones."""

from __future__ import annotations

from types import SimpleNamespace

from naas_abi.apps.nexus.apps.api.app.core import workspace_catalog_seed
from naas_abi.apps.nexus.apps.api.app.core.config import FeatureFlagsConfig
from naas_abi.apps.nexus.apps.api.app.services.feature_access import runtime


def test_settings_is_never_a_switch_of_an_offer(monkeypatch) -> None:
    """An offer (General › Features, a policy's Configuration) switches what a workspace's
    people use; Settings is its administrators', kept whatever the offer says."""
    flags = FeatureFlagsConfig(enabled_features=["chat", "settings", "apps"])
    monkeypatch.setattr(
        workspace_catalog_seed, "live_settings", lambda: SimpleNamespace(feature_flags=flags)
    )

    assert runtime._features() == ["chat", "apps"]
