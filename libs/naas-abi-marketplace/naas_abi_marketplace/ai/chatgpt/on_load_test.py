"""Tests that the chatgpt module registers all its models + the openai
chat/embedding provider factories during on_load."""

from __future__ import annotations

from naas_abi_core.engine.EngineProxy import EngineProxy
from naas_abi_core.engine.IEngine import IEngine
from naas_abi_core.engine.engine_configuration.EngineConfiguration import GlobalConfig
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
    from naas_abi_marketplace.ai.chatgpt import ABIModule

    registry = ModelRegistryService()
    services = IEngine.Services(model_registry=registry)
    engine = _DummyEngine(services=services)
    proxy = EngineProxy(
        engine=engine,
        module_name="naas_abi_marketplace.ai.chatgpt",
        module_dependencies=ModuleDependencies(
            modules=[], services=[ModelRegistryService]
        ),
    )
    config = ABIModule.Configuration(
        global_config=GlobalConfig(ai_mode="cloud"),
        openai_api_key="test-key-not-used",
    )
    module = ABIModule(proxy, config)
    return module, registry


def test_on_load_registers_all_chatgpt_chat_models() -> None:
    module, registry = _make_module()
    module.on_load()

    expected_chat = {
        CanonicalModelId.GPT_5,
        CanonicalModelId.GPT_5_MINI,
        CanonicalModelId.GPT_5_NANO,
        CanonicalModelId.GPT_5_1,
        CanonicalModelId.GPT_5_2,
        CanonicalModelId.GPT_4_1,
        CanonicalModelId.GPT_4_1_MINI,
        CanonicalModelId.GPT_4O,
        CanonicalModelId.O3_MINI,
        CanonicalModelId.O3_DEEP_RESEARCH,
        CanonicalModelId.O4_MINI_DEEP_RESEARCH,
    }
    registered = set(registry.list_canonical_ids())
    assert {str(c) for c in expected_chat} <= registered


def test_on_load_registers_text_embedding_3_large() -> None:
    module, registry = _make_module()
    module.on_load()

    got = registry.get_embedding_model(
        CanonicalModelId.TEXT_EMBEDDING_3_LARGE, provider=ModelProvider.OPENAI
    )
    assert isinstance(got, EmbeddingModel)
    assert got.provider == ModelProvider.OPENAI


def test_on_load_registers_openai_chat_and_embedding_factories_for_off_catalog() -> None:
    module, registry = _make_module()
    module.on_load()

    chat = registry.get_chat_model("gpt-future-model", provider=ModelProvider.OPENAI)
    assert isinstance(chat, ChatModel)
    assert chat.model_id == "gpt-future-model"

    emb = registry.get_embedding_model(
        "text-embedding-future", provider=ModelProvider.OPENAI
    )
    assert isinstance(emb, EmbeddingModel)
    assert emb.model_id == "text-embedding-future"
