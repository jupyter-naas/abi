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


def test_documents_go_to_the_model_in_batches_of_at_most_1024():
    from langchain_core.embeddings import Embeddings
    from naas_abi_core.models.Model import EmbeddingModel
    from naas_abi_core.services.tool_registry.adapters.secondary.ModelRegistryEmbedderAdapter import (
        EMBED_BATCH_SIZE,
    )

    class Recording(Embeddings):
        def __init__(self):
            self.batches: list[int] = []

        def embed_documents(self, texts):
            self.batches.append(len(texts))
            return [[float(len(t)), 1.0] for t in texts]

        def embed_query(self, text):
            return [1.0, 1.0]

    model = Recording()
    registry = ModelRegistryService(default_embedding_model="rec")
    registry.register(
        "rec",
        EmbeddingModel(model_id="rec", provider="fixture", model=model, dimensions=2),
    )
    texts = [f"tool {n}" for n in range(EMBED_BATCH_SIZE * 2 + 5)]

    vectors = ModelRegistryEmbedderAdapter(registry).embed_documents(texts)

    assert EMBED_BATCH_SIZE == 1024
    assert model.batches == [1024, 1024, 5]
    assert [v[0] for v in vectors] == [float(len(t)) for t in texts]


def test_resolve_looks_the_model_up_once():
    looked_up = []

    class Counting(ModelRegistryService):
        def get_default_embedding_model(self):
            looked_up.append(1)
            return super().get_default_embedding_model()

    registry = Counting(default_embedding_model="concepts")
    registry.register("concepts", concept_embedding_model("concepts-v1"))

    resolved = ModelRegistryEmbedderAdapter(registry).resolve()
    resolved.embed_documents(["a", "b"])
    resolved.embed_documents(["c"])
    resolved.embed_query("q")

    assert resolved.model_key == "fixture/concepts-v1"
    assert len(looked_up) == 1
