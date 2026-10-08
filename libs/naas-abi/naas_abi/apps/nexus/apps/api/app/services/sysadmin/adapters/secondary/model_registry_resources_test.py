import asyncio
import json
from urllib.parse import quote

import pytest
from langchain_core.embeddings import Embeddings
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.model_registry_resources import (
    ModelRegistryResources,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.contracts import (
    ReadOnlyResourcesContract,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources import (
    InvalidResource,
    ResourceNotFound,
)
from naas_abi_core.models.Model import ChatModel, EmbeddingModel
from naas_abi_core.services.model_registry.ModelRegistryService import ModelRegistryService


class _Embeddings(Embeddings):
    def embed_documents(self, texts):
        return [[0.0] for _ in texts]

    def embed_query(self, text):
        return [0.0]


def _chat(provider: str, model_id: str, **extra) -> ChatModel:
    return ChatModel(
        model_id=model_id,
        provider=provider,
        model=FakeListChatModel(responses=["hi"]),
        context_window=extra.pop("context_window", 128000),
        **extra,
    )


@pytest.fixture
def registry():
    registry = ModelRegistryService(
        default_chat_model="gpt-5.5", default_embedding_model="text-embedding-3-large"
    )
    registry.register("gpt-5.5", _chat("openai", "gpt-5.5"))
    registry.register("gpt-5.5", _chat("openrouter", "openai/gpt-5.5"))
    registry.register("meta/llama-4", _chat("openrouter", "meta-llama/llama-4"))
    registry.register(
        "text-embedding-3-large",
        EmbeddingModel(model_id="text-embedding-3-large", provider="openai", model=_Embeddings()),
    )
    return registry


class TestModelRegistryResources(ReadOnlyResourcesContract):
    @pytest.fixture
    def resources(self, registry):
        return ModelRegistryResources(registry)


def test_items_are_canonical_ids_with_kind_providers_and_defaults(registry):
    entries = {e.name: e for e in asyncio.run(ModelRegistryResources(registry).list()).entries}

    assert list(entries) == ["gpt-5.5", "meta/llama-4", "text-embedding-3-large"]
    assert entries["gpt-5.5"].attributes == {
        "kind": "chat",
        "providers": "openai, openrouter",
        "default": "chat",
        "context_window": "128000",
    }
    assert entries["meta/llama-4"].id == quote("meta/llama-4", safe="")
    assert entries["text-embedding-3-large"].attributes["default"] == "embedding"


def test_read_shows_every_registered_model_without_the_live_object(registry):
    resources = ModelRegistryResources(registry)

    body = json.loads(asyncio.run(resources.read("gpt-5.5")).content.text)

    assert body["default_for"] == ["chat"]
    assert [(m["provider"], m["model_id"], m["kind"]) for m in body["models"]] == [
        ("openai", "gpt-5.5", "chat"),
        ("openrouter", "openai/gpt-5.5", "chat"),
    ]
    assert body["models"][0]["context_window"] == 128000
    assert "FakeListChatModel" not in json.dumps(body)


def test_models_are_not_folders(registry):
    resources = ModelRegistryResources(registry)

    with pytest.raises(InvalidResource):
        asyncio.run(resources.list("gpt-5.5"))
    with pytest.raises(ResourceNotFound):
        asyncio.run(resources.list("nope"))


def test_entries_carry_name_limits_prices_and_a_one_line_summary():
    registry = ModelRegistryService()
    registry.register(
        "claude-opus-4",
        _chat(
            "openrouter",
            "anthropic/claude-opus-4",
            name="Opus 4",
            description="Claude Opus 4 is a coding model. It sets new benchmarks in many things.",
            context_window=200000,
            pricing={"prompt": "0.000015", "completion": "0.000075"},
            top_provider={"context_length": 200000, "max_completion_tokens": 32000},
        ),
    )
    (entry,) = asyncio.run(ModelRegistryResources(registry).list()).entries

    assert entry.attributes["display_name"] == "Opus 4"
    assert entry.attributes["context_window"] == "200000"
    assert entry.attributes["max_output_tokens"] == "32000"
    assert entry.attributes["input_price"] == "15"
    assert entry.attributes["output_price"] == "75"
    assert entry.attributes["summary"] == "Claude Opus 4 is a coding model."


def test_read_gives_a_model_sheet_view(registry):
    detail = asyncio.run(ModelRegistryResources(registry).read("text-embedding-3-large"))

    assert detail.view["type"] == "json"
    sheet = detail.view["value"]
    assert sheet["canonical_id"] == "text-embedding-3-large"
    assert sheet["default_for"] == ["embedding"]
    assert sheet["models"][0]["kind"] == "embedding"


def test_search_matches_ids_and_names(registry):
    resources = ModelRegistryResources(registry)

    assert resources.capabilities.search is True
    assert [e.name for e in asyncio.run(resources.list(query="LLAMA")).entries] == ["meta/llama-4"]
