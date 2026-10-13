"""Copying LangGraph threads from a checkpoint saver into the document service."""

from __future__ import annotations

import operator
from typing import Annotated, TypedDict
from unittest.mock import MagicMock

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command
from naas_abi_core.services.agent.CheckpointMigration import (
    migrate_checkpoints,
    postgres_source,
    postgres_thread_ids,
)
from naas_abi_core.services.agent.DocumentCheckpointSaver import (
    ENGINE_MEMORY_ID,
    ENGINE_MEMORY_NAMESPACE,
    DocumentCheckpointSaver,
    LegacyDocumentCheckpointReader,
)
from naas_abi_core.services.agent.SqliteCheckpointSaver import SqliteCheckpointSaver
from naas_abi_core.services.agent.tests.checkpoint_saver__generic_test import (
    approval_graph,
    thread,
)
from naas_abi_core.services.agent.tests.langgraph_postgres import langgraph_postgres
from naas_abi_core.services.agent.tests.legacy_checkpoints import v1_saver
from naas_abi_core.services.document.DocumentFactory import DocumentFactory
from naas_abi_core.services.document.DocumentService import DocumentService


class _State(TypedDict):
    log: Annotated[list[str], operator.add]


def nested_graph() -> StateGraph:
    """A parent graph running a subgraph: checkpoints in a child namespace too."""
    child = StateGraph(_State)
    child.add_node("work", lambda state: {"log": ["child"]})
    child.add_edge(START, "work")
    child.add_edge("work", END)
    parent = StateGraph(_State)
    parent.add_node("child", child.compile())
    parent.add_edge(START, "child")
    parent.add_edge("child", END)
    return parent


@pytest.fixture(params=["memory", "sqlite"])
def source(request, tmp_path):
    """A legacy saver holding an interrupted thread and a finished nested one."""
    if request.param == "memory":
        saver = InMemorySaver()
    else:
        saver = SqliteCheckpointSaver(str(tmp_path / "legacy.sqlite"))
    approval_graph().compile(checkpointer=saver).invoke(
        {"log": ["start"]}, thread("pending")
    )
    nested_graph().compile(checkpointer=saver).invoke(
        {"log": ["start"]}, thread("nested")
    )
    return saver


@pytest.fixture
def target(tmp_path):
    root = DocumentService._for_engine(
        DocumentFactory.DocumentAdapterSQLite(str(tmp_path / "documents.sqlite"))
    )
    yield DocumentCheckpointSaver.for_engine(root)
    root.adapter.close()


def everything(saver):
    return list(saver.list(None))


def by_task(item) -> dict[str, list]:
    grouped: dict[str, list] = {}
    for task_id, channel, value in item.pending_writes:
        grouped.setdefault(task_id, []).append((channel, value))
    return grouped


def test_a_dry_run_only_reads_the_source(source):
    history = everything(source)
    summary = migrate_checkpoints(source)
    assert (summary.threads, summary.checkpoints, summary.writes) == (
        2,
        len(history),
        sum(len(item.pending_writes) for item in history),
    )
    assert (summary.copied, summary.present, summary.diverged) == (0, 0, [])
    assert summary.writes > 0  # the pending interrupt


def test_applying_copies_every_checkpoint_and_pending_write(source, target):
    summary = migrate_checkpoints(source, target)
    history = everything(source)
    assert (summary.copied, summary.present) == (len(history), 0)
    assert len(everything(target)) == len(history)
    namespaces = {item.config["configurable"]["checkpoint_ns"] for item in history}
    assert len(namespaces) > 1  # the subgraph's own history came along
    for item in history:
        copied = target.get_tuple(item.config)
        assert copied.config == item.config
        assert copied.parent_config == item.parent_config
        assert copied.metadata == item.metadata
        assert copied.checkpoint["channel_values"] == item.checkpoint["channel_values"]
        assert (
            copied.checkpoint["channel_versions"] == item.checkpoint["channel_versions"]
        )
        assert by_task(copied) == by_task(item)


def test_applying_again_changes_nothing(source, target):
    first = migrate_checkpoints(source, target)
    again = migrate_checkpoints(source, target)
    assert (again.copied, again.present) == (0, first.copied)
    assert len(everything(target)) == first.copied
    assert again.diverged == []


def test_a_migrated_thread_resumes_on_the_document_service(source, target):
    migrate_checkpoints(source, target)
    resumed = (
        approval_graph()
        .compile(checkpointer=target)
        .invoke(Command(resume="yes"), thread("pending"))
    )
    assert resumed["log"] == ["start", "approved:yes"]


def test_threads_continued_before_the_migration_are_reported(source, target):
    # The engine ran on documents before the copy: the conversation's head is
    # newer than the migrated history, which it will not see.
    approval_graph().compile(checkpointer=target).invoke(
        {"log": ["fresh"]}, thread("pending")
    )
    summary = migrate_checkpoints(source, target)
    assert summary.diverged == ["pending"]


def test_selected_threads_only(source, target):
    summary = migrate_checkpoints(source, target, threads=["nested"])
    assert summary.threads == 1
    assert {i.config["configurable"]["thread_id"] for i in everything(target)} == {
        "nested"
    }


def test_an_applied_run_counts_what_the_target_lacked(source, target):
    summary = migrate_checkpoints(source, target)
    assert summary.missing == summary.copied == len(everything(source))


def test_a_dry_run_against_the_target_reports_without_writing(source, target):
    approval_graph().compile(checkpointer=target).invoke(
        {"log": ["fresh"]}, thread("pending")
    )
    before = everything(target)

    summary = migrate_checkpoints(source, target, apply=False)

    assert summary.diverged == ["pending"]
    assert (summary.missing, summary.present, summary.copied) == (
        len(everything(source)),
        0,
        0,
    )
    assert len(everything(target)) == len(before)


def test_a_dry_run_after_the_copy_finds_everything_present(source, target):
    migrate_checkpoints(source, target)

    summary = migrate_checkpoints(source, target, apply=False)

    assert (summary.present, summary.missing, summary.copied) == (
        len(everything(source)),
        0,
        0,
    )
    assert summary.diverged == []


@pytest.fixture
def postgres_url():
    with langgraph_postgres() as url:
        yield url


def test_postgres_source_reads_langgraph_s_tables(postgres_url, target):
    from langgraph.checkpoint.postgres import PostgresSaver

    with PostgresSaver.from_conn_string(postgres_url) as saver:
        approval_graph().compile(checkpointer=saver).invoke(
            {"log": ["start"]}, thread("pending")
        )

    with postgres_source(postgres_url) as (source, thread_ids):
        assert thread_ids == ["pending"]
        summary = migrate_checkpoints(source, target, threads=thread_ids)

    assert summary.copied == summary.checkpoints > 0
    resumed = (
        approval_graph()
        .compile(checkpointer=target)
        .invoke(Command(resume="yes"), thread("pending"))
    )
    assert resumed["log"] == ["start", "approved:yes"]


def test_postgres_thread_ids_come_from_the_checkpoints_table():
    cursor = MagicMock()
    cursor.fetchall.return_value = [{"thread_id": "a"}, {"thread_id": "b"}]
    connection = MagicMock()
    connection.cursor.return_value.__enter__.return_value = cursor
    assert postgres_thread_ids(connection) == ["a", "b"]
    statement = cursor.execute.call_args.args[0]
    assert "DISTINCT thread_id" in statement and "checkpoints" in statement


# --- schema 1 documents to schema 2 ----------------------------------------------------


@pytest.fixture
def engine_namespace(tmp_path):
    root = DocumentService._for_engine(
        DocumentFactory.DocumentAdapterSQLite(str(tmp_path / "engine.sqlite"))
    )
    yield root.for_namespace(ENGINE_MEMORY_NAMESPACE)
    root.adapter.close()


def test_schema_1_threads_copy_to_schema_2_and_continue(engine_namespace):
    legacy = v1_saver(engine_namespace, ENGINE_MEMORY_ID)
    approval_graph().compile(checkpointer=legacy).invoke(
        {"log": ["start"]}, thread("old")
    )
    target = DocumentCheckpointSaver(
        engine_namespace, agent_id=ENGINE_MEMORY_ID, legacy_reads=False
    )
    target.setup()
    source = LegacyDocumentCheckpointReader(engine_namespace, agent_id=ENGINE_MEMORY_ID)
    assert source.thread_ids() == ["old"]

    dry = migrate_checkpoints(source, threads=source.thread_ids())
    applied = migrate_checkpoints(source, target, threads=source.thread_ids())
    again = migrate_checkpoints(source, target, threads=source.thread_ids())
    assert dry.checkpoints == applied.copied == again.present > 0
    assert again.copied == 0
    resumed = (
        approval_graph()
        .compile(checkpointer=target)
        .invoke(Command(resume="yes"), thread("old"))
    )
    assert resumed["log"] == ["start", "approved:yes"]


def test_a_schema_1_thread_already_continued_in_schema_2_is_not_diverged(
    engine_namespace,
):
    legacy = v1_saver(engine_namespace, ENGINE_MEMORY_ID)
    approval_graph().compile(checkpointer=legacy).invoke(
        {"log": ["start"]}, thread("old")
    )
    engine = DocumentCheckpointSaver(engine_namespace, agent_id=ENGINE_MEMORY_ID)
    engine.setup()
    # The engine read the schema 1 head and went on in schema 2.
    approval_graph().compile(checkpointer=engine).invoke(
        Command(resume="ok"), thread("old")
    )

    target = DocumentCheckpointSaver(
        engine_namespace, agent_id=ENGINE_MEMORY_ID, legacy_reads=False
    )
    source = LegacyDocumentCheckpointReader(engine_namespace, agent_id=ENGINE_MEMORY_ID)
    summary = migrate_checkpoints(source, target, threads=source.thread_ids())
    assert summary.diverged == []
    assert summary.copied > 0
