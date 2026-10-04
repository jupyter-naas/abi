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


# --- prune-memory ------------------------------------------------------------------------


def _chat(saver, thread_id: str, turns: int) -> None:
    from langchain_core.messages import AIMessage, HumanMessage
    from langgraph.graph import END, START, MessagesState, StateGraph

    def answer(state):
        turn = len(state["messages"])
        return {"messages": [AIMessage(f"answer {turn} " + "x" * 2000, id=f"a{turn}")]}

    builder = StateGraph(MessagesState)
    builder.add_node("answer", answer)
    builder.add_edge(START, "answer")
    builder.add_edge("answer", END)
    graph = builder.compile(checkpointer=saver)
    for turn in range(turns):
        graph.invoke(
            {
                "messages": [
                    HumanMessage(f"question {turn} " + "q" * 1500, id=f"h{turn}")
                ]
            },
            thread(thread_id),
        )


def _engine_memory(root, namespace=ENGINE_MEMORY_NAMESPACE, agent_id=ENGINE_MEMORY_ID):
    saver = DocumentCheckpointSaver(root.for_namespace(namespace), agent_id=agent_id)
    saver.setup()
    return saver


def prune(*args: str):
    return CliRunner().invoke(agent_cli.agent, ["prune-memory", *args])


def test_prune_memory_keeps_young_values_by_default(documents):
    root, _ = documents
    _chat(_engine_memory(root), "a", 3)

    report = json.loads(prune("--keep-last", "1", "--apply").output)

    assert report["checkpoints"] > 0 and report["values"] == 0  # all under a minute


def test_prune_memory_is_a_dry_run_by_default(documents):
    root, opened = documents
    saver = _engine_memory(root)
    _chat(saver, "a", 3)
    _chat(saver, "b", 2)
    before = len(list(saver.list(thread("a"))))

    result = prune("--keep-last", "1", "--min-age", "0")

    assert result.exit_code == 0, result.output
    report = json.loads(result.output)
    assert (report["mode"], report["threads"], report["keep_last"]) == ("dry-run", 2, 1)
    assert report["checkpoints"] > 0 and report["values"] > 0
    assert report["target"] == {
        "namespace": ENGINE_MEMORY_NAMESPACE,
        "agent_id": ENGINE_MEMORY_ID,
    }
    assert len(list(saver.list(thread("a")))) == before
    assert opened == [ENGINE_MEMORY_NAMESPACE]


def test_prune_memory_applies_and_is_idempotent(documents):
    root, _ = documents
    saver = _engine_memory(root)
    _chat(saver, "a", 3)

    first = json.loads(prune("--keep-last", "1", "--min-age", "0", "--apply").output)
    again = json.loads(prune("--keep-last", "1", "--min-age", "0", "--apply").output)

    assert (
        first["mode"] == "applied" and first["checkpoints"] > 0 and first["values"] > 0
    )
    assert (again["checkpoints"], again["writes"], again["values"]) == (0, 0, 0)
    fresh = _engine_memory(root)
    assert len(list(fresh.list(thread("a")))) == 1
    assert (
        len(fresh.get_tuple(thread("a")).checkpoint["channel_values"]["messages"]) == 6
    )


def test_prune_memory_selects_threads_and_scope(documents):
    root, _ = documents
    scoped = _engine_memory(root, "acme.research", "acme.research.Researcher.v1")
    _chat(scoped, "a", 3)
    _chat(scoped, "b", 3)
    scope = (
        "--namespace",
        "acme.research",
        "--agent-id",
        "acme.research.Researcher.v1",
    )

    report = json.loads(
        prune(*scope, "--thread", "a", "--keep-last", "1", "--apply").output
    )

    assert report["threads"] == 1 and [t["thread_id"] for t in report["pruned"]] == [
        "a"
    ]
    fresh = _engine_memory(root, "acme.research", "acme.research.Researcher.v1")
    assert len(list(fresh.list(thread("a")))) == 1
    assert len(list(fresh.list(thread("b")))) > 1


def test_prune_memory_on_an_empty_store_reports_nothing(documents):
    result = prune()

    assert result.exit_code == 0, result.output
    assert json.loads(result.output)["threads"] == 0
