from __future__ import annotations

import importlib
import json
from contextlib import contextmanager

import pytest
from click.testing import CliRunner
from langgraph.checkpoint.memory import InMemorySaver
from naas_abi_core.services.agent.DocumentCheckpointSaver import (
    ENGINE_MEMORY_ID,
    ENGINE_MEMORY_NAMESPACE,
    DocumentCheckpointSaver,
)
from naas_abi_core.services.agent.tests.checkpoint_saver__generic_test import (
    approval_graph,
    thread,
)
from naas_abi_core.services.agent.tests.legacy_checkpoints import v1_saver
from naas_abi_core.services.document.DocumentFactory import DocumentFactory
from naas_abi_core.services.document.DocumentService import DocumentService

# The package re-exports the click group under the module's name.
agent_cli = importlib.import_module("naas_abi_cli.cli.agent")
SECRET_URL = "postgresql://user:hunter2@db/abi"


@pytest.fixture
def postgres(monkeypatch):
    saver = InMemorySaver()
    approval_graph().compile(checkpointer=saver).invoke(
        {"log": ["start"]}, thread("conversation")
    )
    opened = []

    @contextmanager
    def open_postgres(url):
        opened.append(url)
        yield saver, ["conversation"]

    monkeypatch.setattr(agent_cli, "_postgres_memory", open_postgres)
    return opened


@pytest.fixture
def documents(monkeypatch, tmp_path):
    root = DocumentService._for_engine(
        DocumentFactory.DocumentAdapterSQLite(str(tmp_path / "documents.sqlite"))
    )
    opened = []

    def open_namespace(namespace):
        opened.append(namespace)
        return root.for_namespace(namespace)

    monkeypatch.setattr(agent_cli, "_documents", open_namespace)
    yield root, opened
    root.adapter.close()


def invoke(*args: str):
    return CliRunner().invoke(
        agent_cli.agent, ["migrate-memory", *args], env={"POSTGRES_URL": SECRET_URL}
    )


def head(root, namespace=ENGINE_MEMORY_NAMESPACE, agent_id=ENGINE_MEMORY_ID):
    saver = DocumentCheckpointSaver(
        root.for_namespace(namespace), agent_id=agent_id, legacy_reads=False
    )
    return saver.get_tuple(thread("conversation"))


def test_migrate_memory_is_a_dry_run_by_default(postgres, documents):
    result = invoke()
    assert result.exit_code == 0, result.output
    summary = json.loads(result.output)
    assert (summary["mode"], summary["source"]) == ("dry-run", "postgres")
    assert (summary["threads"], summary["copied"]) == (1, 0)
    assert summary["checkpoints"] > 0
    assert postgres == [SECRET_URL]
    assert documents[1] == []  # the document service is not even opened
    assert "hunter2" not in result.output


def test_migrate_memory_applies_and_is_idempotent(postgres, documents):
    first = json.loads(invoke("--apply").output)
    again = json.loads(invoke("--apply").output)
    assert first["mode"] == "applied"
    assert first["copied"] == first["checkpoints"] > 0
    assert (again["copied"], again["present"]) == (0, first["copied"])
    assert first["target"] == {
        "namespace": ENGINE_MEMORY_NAMESPACE,
        "agent_id": ENGINE_MEMORY_ID,
        "schema": 2,
    }
    assert head(documents[0]) is not None


def test_migrate_memory_copies_schema_1_documents_of_any_scope(documents):
    root, _ = documents
    legacy = v1_saver(
        root.for_namespace("acme.research"), "acme.research.Researcher.v1"
    )
    approval_graph().compile(checkpointer=legacy).invoke(
        {"log": ["start"]}, thread("conversation")
    )
    scope = (
        "--namespace",
        "acme.research",
        "--agent-id",
        "acme.research.Researcher.v1",
    )

    dry = json.loads(invoke("--from", "documents-v1", *scope).output)
    applied = json.loads(invoke("--from", "documents-v1", *scope, "--apply").output)

    assert (dry["source"], dry["threads"], dry["copied"]) == ("documents-v1", 1, 0)
    assert applied["copied"] == dry["checkpoints"] > 0
    assert head(root, "acme.research", "acme.research.Researcher.v1") is not None


def test_migrate_memory_needs_a_source(postgres):
    result = CliRunner().invoke(
        agent_cli.agent, ["migrate-memory"], env={"POSTGRES_URL": ""}
    )
    assert result.exit_code != 0
    assert "POSTGRES_URL" in result.output
    assert postgres == []
