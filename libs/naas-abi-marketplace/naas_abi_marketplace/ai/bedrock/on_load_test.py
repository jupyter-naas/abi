"""Tests that the bedrock module registers its models + provider factory
against the ModelRegistry during on_load.

Credential validation is disabled here via the BEDROCK_SKIP_VALIDATION env
var (set at import time below) — the registry wiring is what's under test,
not the AWS access path."""

from __future__ import annotations

import os

# Disable AWS connectivity check during Configuration validation. Must be set
# before the module is imported.
os.environ["BEDROCK_SKIP_VALIDATION"] = "1"

from naas_abi_core.engine.EngineProxy import EngineProxy  # noqa: E402
from naas_abi_core.engine.IEngine import IEngine  # noqa: E402
from naas_abi_core.engine.engine_configuration.EngineConfiguration import (  # noqa: E402
    GlobalConfig,
)
from naas_abi_core.models.Model import (  # noqa: E402
    CanonicalModelId,
    ChatModel,
    ModelProvider,
)
from naas_abi_core.module.Module import ModuleDependencies  # noqa: E402
from naas_abi_core.services.model_registry.ModelRegistryService import (  # noqa: E402
    ModelRegistryService,
)


class _DummyEngine:
    def __init__(self, services: IEngine.Services) -> None:
        self.services = services
        self.modules: dict[str, object] = {}


def _make_module():
    from naas_abi_marketplace.ai.bedrock import ABIModule

    registry = ModelRegistryService()
    services = IEngine.Services(model_registry=registry)
    engine = _DummyEngine(services=services)
    proxy = EngineProxy(
        engine=engine,
        module_name="naas_abi_marketplace.ai.bedrock",
        module_dependencies=ModuleDependencies(
            modules=[], services=[ModelRegistryService]
        ),
    )
    config = ABIModule.Configuration(
        global_config=GlobalConfig(ai_mode="cloud"),
        aws_access_key_id="test-key",
        aws_secret_access_key="test-secret",
        region_name="us-east-1",
        validate_on_load=False,
    )
    module = ABIModule(proxy, config)
    return module, registry


def test_on_load_registers_all_four_bedrock_models() -> None:
    module, registry = _make_module()
    module.on_load()

    expected = {
        CanonicalModelId.CLAUDE_SONNET_4,
        CanonicalModelId.CLAUDE_HAIKU_3_5,
        CanonicalModelId.LLAMA_3_3_70B,
        CanonicalModelId.NOVA_PRO,
    }
    registered = set(registry.list_canonical_ids())
    assert {str(c) for c in expected} <= registered


def test_bedrock_models_are_pinned_to_bedrock_provider() -> None:
    module, registry = _make_module()
    module.on_load()

    got = registry.get_chat_model(
        CanonicalModelId.CLAUDE_SONNET_4, provider=ModelProvider.BEDROCK
    )
    assert isinstance(got, ChatModel)
    assert got.provider == ModelProvider.BEDROCK


def test_off_catalog_bedrock_lookup_uses_factory() -> None:
    module, registry = _make_module()
    module.on_load()

    got = registry.get_chat_model(
        "anthropic.claude-future-model-v1:0", provider=ModelProvider.BEDROCK
    )
    assert isinstance(got, ChatModel)
    assert got.provider == ModelProvider.BEDROCK
    assert got.model_id == "anthropic.claude-future-model-v1:0"
