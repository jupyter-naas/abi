"""Engine.load binds agent memory to the document service; shutdown unbinds it."""

from __future__ import annotations

import pytest
from naas_abi_core.engine.context import (
    get_default_agent_checkpointer,
    set_default_agent_checkpointer,
)
from naas_abi_core.engine.Engine import Engine
from naas_abi_core.engine.engine_loaders.EngineModuleLoader import EngineModuleLoader
from naas_abi_core.module.Module import ModuleDependencies
from naas_abi_core.services.agent.Agent import create_checkpointer
from naas_abi_core.services.agent.DocumentCheckpointSaver import (
    ENGINE_MEMORY_ID,
    ENGINE_MEMORY_NAMESPACE,
    DocumentCheckpointSaver,
)
from naas_abi_core.services.document.DocumentService import DocumentService


@pytest.fixture(autouse=True)
def _unbound():
    set_default_agent_checkpointer(None)
    yield
    set_default_agent_checkpointer(None)


def engine(tmp_path, monkeypatch, services: list[type]) -> Engine:
    # One module whose declared services decide what the engine loads.
    monkeypatch.setattr(
        EngineModuleLoader,
        "get_modules_dependencies",
        lambda self, names: {
            "probe": ModuleDependencies(modules=[], services=services)
        },
    )
    monkeypatch.setattr(EngineModuleLoader, "load_modules", lambda self, e, names: {})
    path = tmp_path / "documents.sqlite"
    return Engine(
        "api: {}\n"
        "global_config: {ai_mode: cloud, skip_ontology_loading: true}\n"
        "modules: []\n"
        "services:\n"
        "  secret: {secret_adapters: []}\n"
        f"  document: {{document_adapter: {{adapter: sqlite, config: {{path: '{path}'}}}}}}\n"
    )


def test_agents_built_in_a_loaded_engine_checkpoint_into_documents(
    tmp_path, monkeypatch
):
    loaded = engine(tmp_path, monkeypatch, [DocumentService])
    loaded.load()
    memory = get_default_agent_checkpointer()
    assert isinstance(memory, DocumentCheckpointSaver)
    assert memory.documents.namespace == ENGINE_MEMORY_NAMESPACE
    assert memory.agent_id == ENGINE_MEMORY_ID
    assert create_checkpointer() is memory

    loaded.shutdown()
    assert get_default_agent_checkpointer() is None


def test_an_engine_without_documents_keeps_the_standalone_fallback(
    tmp_path, monkeypatch
):
    set_default_agent_checkpointer(object())  # type: ignore[arg-type]
    loaded = engine(tmp_path, monkeypatch, [])
    loaded.load()
    assert get_default_agent_checkpointer() is None
    loaded.shutdown()


def test_shutdown_leaves_another_engines_memory_bound(tmp_path, monkeypatch):
    first = engine(tmp_path / "a", monkeypatch, [DocumentService])
    second = engine(tmp_path / "b", monkeypatch, [DocumentService])
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    first.load()
    second.load()
    current = get_default_agent_checkpointer()
    first.shutdown()
    assert get_default_agent_checkpointer() is current
    second.shutdown()
    assert get_default_agent_checkpointer() is None
