"""Tests that the openrouter module registers its models against the
ModelRegistry during on_load — focused on the OpenAI embedding models
routed through the OpenRouter gateway, plus the Gemma 4 chat models a
generated project defaults to."""

from __future__ import annotations

from naas_abi_core.engine.engine_configuration.EngineConfiguration import GlobalConfig
from naas_abi_core.engine.EngineProxy import EngineProxy
from naas_abi_core.engine.IEngine import IEngine
from naas_abi_core.models.Model import (
    CanonicalModelId,
    ChatModel,
    EmbeddingModel,
    ModelProvider,
)
from naas_abi_core.module.Module import ModuleDependencies
from naas_abi_core.services.model_registry.ModelRegistryService import (
    ModelRegistryService,
)


class _DummyEngine:
    def __init__(self, services: IEngine.Services) -> None:
        self.services = services
        self.modules: dict[str, object] = {}


def _make_module():
    from naas_abi_marketplace.ai.openrouter import ABIModule

    registry = ModelRegistryService()
    services = IEngine.Services(model_registry=registry)
    engine = _DummyEngine(services=services)
    proxy = EngineProxy(
        engine=engine,
        module_name="naas_abi_marketplace.ai.openrouter",
        module_dependencies=ModuleDependencies(
            modules=[], services=[ModelRegistryService]
        ),
    )
    config = ABIModule.Configuration(
        global_config=GlobalConfig(ai_mode="cloud"),
        openrouter_api_key="test-key-not-used",
    )
    module = ABIModule(proxy, config)
    return module, registry


def test_on_load_registers_openai_embedding_models() -> None:
    module, registry = _make_module()
    module.on_load()

    expected = {
        CanonicalModelId.TEXT_EMBEDDING_3_SMALL,
        CanonicalModelId.TEXT_EMBEDDING_3_LARGE,
        CanonicalModelId.TEXT_EMBEDDING_ADA_002,
    }
    registered = set(registry.list_canonical_ids())
    assert {str(c) for c in expected} <= registered


def test_openai_embeddings_register_as_embedding_models_on_openrouter() -> None:
    module, registry = _make_module()
    module.on_load()

    cases = {
        CanonicalModelId.TEXT_EMBEDDING_3_SMALL: "openai/text-embedding-3-small",
        CanonicalModelId.TEXT_EMBEDDING_3_LARGE: "openai/text-embedding-3-large",
        CanonicalModelId.TEXT_EMBEDDING_ADA_002: "openai/text-embedding-ada-002",
    }
    for canonical_id, model_id in cases.items():
        got = registry.get_embedding_model(
            canonical_id, provider=ModelProvider.OPENROUTER
        )
        assert isinstance(got, EmbeddingModel)
        assert got.provider == ModelProvider.OPENROUTER
        assert got.model_id == model_id


def test_gemma_4_chat_models_register_on_openrouter() -> None:
    """`abi new project` points default_chat_model at gemma-4-26b-a4b-it, and
    names gemma-4-31b-it as the swap-in alternative — both must resolve here or
    a generated project fails its post-load default validation."""
    module, registry = _make_module()
    module.on_load()

    cases = {
        CanonicalModelId.GEMMA_4_26B_A4B_IT: "google/gemma-4-26b-a4b-it",
        CanonicalModelId.GEMMA_4_31B_IT: "google/gemma-4-31b-it",
    }
    for canonical_id, model_id in cases.items():
        got = registry.get_chat_model(canonical_id, provider=ModelProvider.OPENROUTER)
        assert isinstance(got, ChatModel)
        assert got.provider == ModelProvider.OPENROUTER
        assert got.model_id == model_id
