"""Tests that the anthropic module registers its models + provider factory
against the ModelRegistry during on_load."""

from __future__ import annotations

from naas_abi_core.engine.EngineProxy import EngineProxy
from naas_abi_core.engine.IEngine import IEngine
from naas_abi_core.engine.engine_configuration.EngineConfiguration import GlobalConfig
from naas_abi_core.models.Model import CanonicalModelId, ChatModel, ModelProvider
from naas_abi_core.module.Module import ModuleDependencies
from naas_abi_core.services.model_registry.ModelRegistryService import (
    ModelRegistryService,
)


class _DummyEngine:
    def __init__(self, services: IEngine.Services) -> None:
        self.services = services
        self.modules: dict[str, object] = {}


def _make_module():
    from naas_abi_marketplace.ai.anthropic import ABIModule

    registry = ModelRegistryService(default_chat_model="claude-sonnet-4.5")
    services = IEngine.Services(model_registry=registry)
    engine = _DummyEngine(services=services)
    proxy = EngineProxy(
        engine=engine,
        module_name="naas_abi_marketplace.ai.anthropic",
        module_dependencies=ModuleDependencies(
            modules=[], services=[ModelRegistryService]
        ),
    )
    config = ABIModule.Configuration(
        global_config=GlobalConfig(ai_mode="cloud"),
        anthropic_api_key="test-key-not-used",
    )
    module = ABIModule(proxy, config)
    return module, registry


def test_on_load_registers_all_six_claude_models() -> None:
    module, registry = _make_module()
    module.on_load()

    expected = {
        CanonicalModelId.CLAUDE_SONNET_4_5,
        CanonicalModelId.CLAUDE_SONNET_4,
        CanonicalModelId.CLAUDE_SONNET_3_7,
        CanonicalModelId.CLAUDE_OPUS_4_1,
        CanonicalModelId.CLAUDE_OPUS_4,
        CanonicalModelId.CLAUDE_HAIKU_4_5,
    }
    registered = set(registry.list_canonical_ids())
    assert {str(c) for c in expected} <= registered


def test_on_load_makes_get_chat_model_work_for_default() -> None:
    module, registry = _make_module()
    module.on_load()

    # validate_defaults should pass since the default is now registered.
    registry.validate_defaults()

    got = registry.get_default_chat_model()
    assert isinstance(got, ChatModel)
    assert got.provider == ModelProvider.ANTHROPIC


def test_on_load_registers_anthropic_chat_provider_for_off_catalog() -> None:
    module, registry = _make_module()
    module.on_load()

    # A canonical id not registered should still resolve via the anthropic
    # chat factory when caller pins the provider.
    got = registry.get_chat_model(
        "claude-future-model", provider=ModelProvider.ANTHROPIC
    )
    assert isinstance(got, ChatModel)
    assert got.provider == ModelProvider.ANTHROPIC
    assert got.model_id == "claude-future-model"
