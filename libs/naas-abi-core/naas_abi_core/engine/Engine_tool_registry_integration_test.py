"""The tool registry in every engine role, on a real broker and without NATS.

Each process has its own registry: modules publish to it where they load, and
only its search backend crosses NATS. See
docs/adr/20260923_tool-registry-and-agent-composition.md.
"""

import textwrap
from pathlib import Path

import pytest
from naas_abi_core.engine.nats_test_server import native_nats_server, nats_server_binary
from naas_abi_core.services.tool_registry.ToolRegistryPort import ToolContext

SECRET = "engine-tool-registry-test-secret-at-least-32-bytes"
ISSUE = "tool_probe/create_issue@1"
FORECAST = "tool_probe/get_forecast@1"

PROBE_MODULE = textwrap.dedent(
    '''
    from langchain_core.tools import tool
    from naas_abi_core.module.Module import (
        BaseModule,
        ModuleConfiguration,
        ModuleDependencies,
    )
    from naas_abi_core.services.tool_registry.tests.concept_embeddings import (
        concept_embedding_model,
    )
    from naas_abi_core.services.vector_store.VectorStoreService import (
        VectorStoreService,
    )


    @tool
    def create_issue(title: str) -> str:
        """Create a new issue in a GitHub repository."""
        return title


    @tool
    def get_forecast(city: str) -> str:
        """Get the weather forecast for a city."""
        return city


    class ABIModule(BaseModule):
        dependencies = ModuleDependencies(
            modules=[], services=[VectorStoreService]
        )

        class Configuration(ModuleConfiguration):
            pass

        def on_load(self):
            self._engine.services.model_registry.register(
                "concepts", concept_embedding_model()
            )

        def publish_tools(self, publisher):
            publisher.add_tools([create_issue, get_forecast])
    '''
)


@pytest.fixture
def probe(tmp_path, monkeypatch) -> None:
    package = tmp_path / "modules" / "tool_probe"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text(PROBE_MODULE)
    monkeypatch.syspath_prepend(str(tmp_path / "modules"))


@pytest.fixture
def engine_dir(tmp_path, monkeypatch) -> Path:
    work = tmp_path / "engine"
    work.mkdir()
    monkeypatch.chdir(work)
    return work


@pytest.fixture
def broker(tmp_path):
    if nats_server_binary() is None:
        pytest.skip("nats-server is not installed")
    with native_nats_server(tmp_path, jetstream=True) as url:
        yield url


def new_engine(url: str | None = None, **engine):
    from naas_abi_core.engine.Engine import Engine

    nats = ""
    if url is not None:
        settings = ", ".join(f"{key}: {value}" for key, value in engine.items())
        nats = (
            f"nats: {{nats_url: '{url}', jwt_secret: {SECRET}, "
            f"engine: {{{settings}}}}}\n"
        )
    return Engine(
        "api: {}\n"
        "global_config: {ai_mode: cloud, skip_ontology_loading: true}\n"
        "modules: [{module: tool_probe, enabled: true, config: {}}]\n"
        "services:\n"
        "  secret: {secret_adapters: []}\n"
        "  model_registry: {default_embedding_model: concepts}\n"
        "  tool_registry: {collection_prefix: probe_tools}\n" + nats
    )


def tool_collections(engine) -> list[str]:
    """What the serving engine's vector store holds for the tool index."""
    owner = engine._Engine__services.vector_store  # noqa: SLF001 - the owner's, not a facade
    return [c for c in owner.list_collections() if c.startswith("probe_tools__")]


def indexed_ids(engine) -> set[str]:
    owner = engine._Engine__services.vector_store  # noqa: SLF001
    (collection,) = tool_collections(engine)
    return {
        document.metadata["tool_id"]
        for document in owner.list_documents(collection).documents
    }


def assert_published_and_searchable(engine) -> None:
    services = engine.services
    assert services.tool_registry_available()
    assert {str(d.id) for d in services.tool_registry.list_definitions()} == {
        ISSUE,
        FORECAST,
    }
    hits = services.tool_registry.search_tools(
        "report a bug", ToolContext(), limit=1
    )
    assert [hit.tool_id for hit in hits] == [ISSUE]


def test_with_nats_off_the_registry_is_populated_and_searchable(probe, engine_dir):
    engine = new_engine()
    engine.load()
    try:
        assert_published_and_searchable(engine)
        assert len(tool_collections(engine)) == 1
    finally:
        engine.shutdown()


def test_a_serving_engine_publishes_and_indexes_in_the_shared_store(
    probe, engine_dir, broker
):
    engine = new_engine(broker)
    engine.load()
    try:
        assert_published_and_searchable(engine)
        assert indexed_ids(engine) == {ISSUE, FORECAST}
        # The facade modules get hands out the process's own registry.
        assert engine.services.tool_registry is engine._Engine__services.tool_registry  # noqa: SLF001
    finally:
        engine.shutdown()


def test_a_client_engine_publishes_its_tools_and_never_writes_the_shared_index(
    probe, engine_dir, broker
):
    serving = new_engine(broker)
    serving.load()
    client = new_engine(broker, role="client")
    client.load()
    try:
        assert client.services.tool_registry is not serving.services.tool_registry
        assert_published_and_searchable(serving)
        assert indexed_ids(serving) == {ISSUE, FORECAST}
        assert_published_and_searchable(client)
        assert indexed_ids(serving) == {ISSUE, FORECAST}
        assert len(tool_collections(serving)) == 1
    finally:
        client.shutdown()
        serving.shutdown()
