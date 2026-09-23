import pytest
from naas_abi_core.services.model_registry.ModelRegistryService import (
    ModelRegistryService,
)
from naas_abi_core.services.tool_registry.adapters.secondary.ModelRegistryEmbedderAdapter import (
    ModelRegistryEmbedderAdapter,
)
from naas_abi_core.services.tool_registry.tests.concept_embeddings import (
    concept_embedding_model,
    concept_vector,
)
from naas_abi_core.services.tool_registry.ToolRegistryPort import (
    IToolEmbedderPort,
    ToolSearchUnavailableError,
)


@pytest.fixture
def registry() -> ModelRegistryService:
    registry = ModelRegistryService(default_embedding_model="concepts")
    registry.register("concepts", concept_embedding_model("concepts-v1"))
    registry.register("concepts-next", concept_embedding_model("concepts-v2"))
    return registry


def test_is_an_embedder_port(registry):
    assert isinstance(ModelRegistryEmbedderAdapter(registry), IToolEmbedderPort)


def test_uses_the_default_embedding_model(registry):
    embedder = ModelRegistryEmbedderAdapter(registry)
    assert embedder.model_key == "fixture/concepts-v1"
    assert embedder.embed_query("open a ticket") == concept_vector("open a ticket")
    assert embedder.embed_documents(["a bug", "the weather"]) == [
        concept_vector("a bug"),
        concept_vector("the weather"),
    ]


def test_can_pin_a_canonical_model(registry):
    embedder = ModelRegistryEmbedderAdapter(registry, canonical_id="concepts-next")
    assert embedder.model_key == "fixture/concepts-v2"


def test_follows_a_default_model_change(registry):
    embedder = ModelRegistryEmbedderAdapter(registry)
    before = embedder.model_key
    registry._default_embedding_model = "concepts-next"
    assert embedder.model_key != before


def test_a_missing_embedding_model_is_an_explicit_search_error():
    embedder = ModelRegistryEmbedderAdapter(ModelRegistryService())
    with pytest.raises(ToolSearchUnavailableError, match="embedding model"):
        embedder.embed_query("anything")
