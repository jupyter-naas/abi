"""Tests that the ollama module registers its local chat + embedding models and
the ollama provider factories during on_load — with no server running and no
credentials."""

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


def _make_module(**config_overrides):
    from naas_abi_marketplace.ai.ollama import ABIModule

    registry = ModelRegistryService()
    services = IEngine.Services(model_registry=registry)
    engine = _DummyEngine(services=services)
    proxy = EngineProxy(
        engine=engine,
        module_name="naas_abi_marketplace.ai.ollama",
        module_dependencies=ModuleDependencies(
            modules=[], services=[ModelRegistryService]
        ),
    )
    config = ABIModule.Configuration(
        global_config=GlobalConfig(ai_mode="local"),
        # No probing: these tests must pass whether or not a server is up.
        probe_on_load=False,
        **config_overrides,
    )
    module = ABIModule(proxy, config)
    return module, registry


def test_on_load_needs_no_api_key() -> None:
    """The whole point of the module: it configures with zero credentials."""
    module, _ = _make_module()
    module.on_load()


def test_on_load_registers_qwen_2_5_3b_as_a_chat_model() -> None:
    module, registry = _make_module()
    module.on_load()

    got = registry.get_chat_model(
        CanonicalModelId.QWEN_2_5_3B, provider=ModelProvider.OLLAMA
    )
    assert isinstance(got, ChatModel)
    assert got.provider == ModelProvider.OLLAMA
    assert got.model_id == "qwen2.5:3b"


def test_on_load_registers_a_local_embedding_model() -> None:
    module, registry = _make_module()
    module.on_load()

    got = registry.get_embedding_model(
        CanonicalModelId.NOMIC_EMBED_TEXT, provider=ModelProvider.OLLAMA
    )
    assert isinstance(got, EmbeddingModel)
    assert got.provider == ModelProvider.OLLAMA
    assert got.dimensions == 768


def test_registered_defaults_cover_both_model_types() -> None:
    """A keyless project needs chat *and* embeddings, or the vector store dies."""
    module, registry = _make_module()
    module.on_load()

    registered = set(registry.list_canonical_ids())
    assert {"qwen-2.5-3b", "nomic-embed-text"} <= registered


def test_on_load_registers_ollama_factories_for_off_catalog_models() -> None:
    """Any ollama tag should work without shipping a model file for it — the
    escape hatch for swapping in a lighter or heavier local model."""
    module, registry = _make_module()
    module.on_load()

    chat = registry.get_chat_model("qwen2.5:1.5b", provider=ModelProvider.OLLAMA)
    assert isinstance(chat, ChatModel)
    assert chat.model_id == "qwen2.5:1.5b"

    emb = registry.get_embedding_model(
        "some-future-embedder", provider=ModelProvider.OLLAMA
    )
    assert isinstance(emb, EmbeddingModel)
    assert emb.model_id == "some-future-embedder"


def test_configured_base_url_is_used_verbatim() -> None:
    module, _ = _make_module(base_url="http://ollama.box:9999")
    module.on_load()
    assert module.base_url == "http://ollama.box:9999"


def test_base_url_is_visible_to_model_files_during_load() -> None:
    """Model files read the endpoint at import time, which happens inside
    on_load — so resolution must precede model discovery."""
    from naas_abi_marketplace.ai.ollama import ABIModule

    module, _ = _make_module(base_url="http://ollama.box:9999")
    module.on_load()
    assert ABIModule.resolved_base_url() == "http://ollama.box:9999"
