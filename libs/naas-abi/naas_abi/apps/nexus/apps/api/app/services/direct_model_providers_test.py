from __future__ import annotations

import pytest
from naas_abi.apps.nexus.apps.api.app.core import config
from naas_abi.apps.nexus.apps.api.app.services.direct_model_providers import (
    DirectModelProviderDisabledError,
    direct_model_providers_enabled,
    ensure_direct_model_providers_enabled,
)


def test_direct_model_providers_are_on_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DIRECT_MODEL_PROVIDERS_ENABLED", raising=False)

    assert config.Settings().direct_model_providers_enabled is True


def test_the_setting_is_read_from_the_settings_naas_abi_installs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``naas_abi`` replaces ``config.settings`` once the engine is loaded: the
    guard reads that object at call time, never one captured at import."""
    monkeypatch.setattr(config, "settings", config.Settings(direct_model_providers_enabled=False))

    assert direct_model_providers_enabled() is False
    with pytest.raises(DirectModelProviderDisabledError) as refused:
        ensure_direct_model_providers_enabled("Speech synthesis", hint="Register a model.")

    assert str(refused.value) == (
        "Speech synthesis calls a model provider directly, outside the model registry, "
        "and direct model providers are turned off on this deployment "
        "(direct_model_providers_enabled: false). Register a model."
    )


def test_nothing_is_refused_while_direct_model_providers_are_on(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(config.settings, "direct_model_providers_enabled", True)

    ensure_direct_model_providers_enabled("Speech synthesis")
