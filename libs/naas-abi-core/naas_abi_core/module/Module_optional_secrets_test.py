"""optional_secrets: a module loads without marketplace keys."""

from __future__ import annotations

import pytest
from naas_abi_core.engine.engine_configuration.EngineConfiguration import GlobalConfig
from naas_abi_core.module.Module import BaseModule, ModuleConfiguration


class _RequiredConfig(ModuleConfiguration):
    token: str


class _OptionalConfig(ModuleConfiguration):
    token: str = ""
    extra: str = "keep"


class _RequiredModule(BaseModule[_RequiredConfig]):
    Configuration = _RequiredConfig


class _OptionalModule(BaseModule[_OptionalConfig]):
    Configuration = _OptionalConfig
    optional_secrets = True
    secret_fields = {"token": "DEMO_TOKEN"}


def _global() -> GlobalConfig:
    return GlobalConfig(ai_mode="cloud")


class _Secrets:
    def __init__(self, values: dict[str, str]) -> None:
        self._values = values

    def get(self, key: str, default: str | None = None) -> str | None:
        return self._values.get(key, default)


def test_a_required_secret_still_fails_module_load() -> None:
    with pytest.raises(ValueError, match="Error loading configuration"):
        _RequiredModule.build_configuration(_global(), {})


def test_optional_secrets_load_with_defaults_when_keys_are_missing() -> None:
    cfg = _OptionalModule.build_configuration(_global(), {})
    assert cfg.token == ""
    assert cfg.extra == "keep"


def test_optional_secrets_are_read_from_the_secret_service_at_module_load() -> None:
    cfg = _OptionalModule.build_configuration(
        _global(), {}, secrets=_Secrets({"DEMO_TOKEN": "from-service"})
    )
    assert cfg.token == "from-service"


def test_yaml_config_wins_over_the_secret_service() -> None:
    cfg = _OptionalModule.build_configuration(
        _global(),
        {"token": "from-yaml"},
        secrets=_Secrets({"DEMO_TOKEN": "from-service"}),
    )
    assert cfg.token == "from-yaml"