"""Engine agent memory as kernel jobs: the migration an admin runs, and pruning."""

from __future__ import annotations

import operator
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Annotated, TypedDict

import psycopg
import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command
from naas_abi_core.module.jobs import Cron, JobContext
from naas_abi_core.services.agent.AgentMemoryJobs import (
    AGENT_MEMORY_JOBS_OWNER,
    AgentMemoryJobs,
    postgres_url_from,
)
from naas_abi_core.services.agent.DocumentCheckpointSaver import (
    ENGINE_MEMORY_ID,
    ENGINE_MEMORY_NAMESPACE,
    DocumentCheckpointSaver,
)
from naas_abi_core.services.agent.tests.checkpoint_saver__generic_test import (
    approval_graph,
    thread,
)
from naas_abi_core.services.agent.tests.langgraph_postgres import langgraph_postgres
from naas_abi_core.services.agent.tests.legacy_checkpoints import v1_saver
from naas_abi_core.services.document.DocumentFactory import DocumentFactory
from naas_abi_core.services.document.DocumentService import DocumentService

SECRET_URL = "postgresql://memory:s3cr3t-pa55@db.internal:5432/abi"


class _State(TypedDict):
    log: Annotated[list[str], operator.add]


def counting_graph() -> StateGraph:
    builder = StateGraph(_State)
    builder.add_node("step", lambda state: {"log": ["step"]})
    builder.add_edge(START, "step")
    builder.add_edge("step", END)
    return builder


@pytest.fixture
def memory(tmp_path):
    """The engine's agent checkpointer, as ``Engine.load`` binds it."""
    root = DocumentService._for_engine(
        DocumentFactory.DocumentAdapterSQLite(str(tmp_path / "documents.sqlite"))
    )
    yield DocumentCheckpointSaver.for_engine(root)
    root.adapter.close()


@pytest.fixture
def legacy():
    """LangGraph's PostgreSQL memory, stood in by an in-memory saver."""
    saver = InMemorySaver()
    approval_graph().compile(checkpointer=saver).invoke(
        {"log": ["start"]}, thread("pending")
    )
    counting_graph().compile(checkpointer=saver).invoke(
        {"log": ["start"]}, thread("finished")
    )
    return saver


class Opener:
    """Records the URL it was given; serves ``saver`` as the PostgreSQL source."""

    def __init__(self, saver):
        self.saver = saver
        self.urls: list[str] = []

    @contextmanager
    def __call__(self, url):
        self.urls.append(url)
        ids = sorted(
            {i.config["configurable"]["thread_id"] for i in self.saver.list(None)}
        )
        yield self.saver, ids


def jobs(memory, legacy=None, url=SECRET_URL):
    opener = Opener(legacy or InMemorySaver())
    owner = AgentMemoryJobs(memory, postgres_url=lambda: url, open_postgres=opener)
    return owner, opener


def ctx(payload=None, job="agent_memory_migrate"):
    return JobContext("run-1", job, 1, {"kind": "manual"}, payload or {})


def stored(saver) -> int:
    return len(list(saver.list(None)))


# --- declarations ------------------------------------------------------------------------


def test_migration_runs_only_on_demand_and_pruning_daily():
    declared = {j.name: j for j in AgentMemoryJobs.jobs}

    assert AGENT_MEMORY_JOBS_OWNER == "naas_abi_core.agent_memory"
    assert set(declared) == {"agent_memory_migrate", "agent_memory_prune"}
    assert declared["agent_memory_migrate"].triggers == ()
    assert declared["agent_memory_prune"].triggers == (
        Cron("0 0 3 * * *", time_zone="UTC"),
    )


def test_every_job_has_a_handler(memory):
    owner, _ = jobs(memory)
    assert owner.missing_job_handlers() == set()


# --- agent_memory_migrate ----------------------------------------------------------------


def test_the_migration_is_a_dry_run_by_default(memory, legacy):
    owner, opener = jobs(memory, legacy)

    report = owner.migrate(ctx())

    assert opener.urls == [SECRET_URL]
    assert report["mode"] == "dry-run"
    assert report["source"] == "postgres"
    assert report["target"] == {
        "namespace": ENGINE_MEMORY_NAMESPACE,
        "agent_id": ENGINE_MEMORY_ID,
        "schema": 2,
    }
    assert report["threads"] == 2
    assert report["missing"] == report["checkpoints"] == stored(legacy)
    assert (report["copied"], report["present"], report["diverged"]) == (0, 0, [])
    assert stored(memory) == 0


def test_applying_copies_the_threads_and_they_resume(memory, legacy):
    owner, _ = jobs(memory, legacy)

    report = owner.migrate(ctx({"apply": True}))

    assert report["mode"] == "applied"
    assert report["copied"] == report["checkpoints"] == stored(legacy)
    resumed = (
        approval_graph()
        .compile(checkpointer=memory)
        .invoke(Command(resume="yes"), thread("pending"))
    )
    assert resumed["log"] == ["start", "approved:yes"]
    again = owner.migrate(ctx({"apply": True}))
    assert (again["copied"], again["present"]) == (0, report["copied"])


def test_only_the_selected_threads_are_copied(memory, legacy):
    owner, _ = jobs(memory, legacy)

    report = owner.migrate(ctx({"threads": ["finished"], "apply": True}))

    assert report["threads"] == 1
    assert {i.config["configurable"]["thread_id"] for i in memory.list(None)} == {
        "finished"
    }


def test_the_dry_run_lists_threads_continued_before_the_migration(memory, legacy):
    # A user went on with an old conversation between the deploy and the job.
    approval_graph().compile(checkpointer=memory).invoke(
        {"log": ["fresh"]}, thread("pending")
    )
    owner, _ = jobs(memory, legacy)
    context = ctx()

    report = owner.migrate(context)

    assert report["diverged"] == ["pending"]
    assert any("diverged" in line for line in context.logs)


def test_schema_1_documents_copy_into_schema_2(memory):
    old = v1_saver(memory.documents, ENGINE_MEMORY_ID)
    approval_graph().compile(checkpointer=old).invoke({"log": ["start"]}, thread("v1"))
    owner, opener = jobs(memory)

    report = owner.migrate(ctx({"from": "documents-v1", "apply": True}))

    assert opener.urls == []  # PostgreSQL is not read
    assert report["source"] == "documents-v1"
    assert report["threads"] == 1 and report["copied"] > 0
    resumed = (
        approval_graph()
        .compile(checkpointer=memory)
        .invoke(Command(resume="ok"), thread("v1"))
    )
    assert resumed["log"] == ["start", "approved:ok"]


def test_without_schema_1_documents_there_is_nothing_to_copy(memory):
    owner, _ = jobs(memory)

    report = owner.migrate(ctx({"from": "documents-v1"}))

    assert report["threads"] == 0


@pytest.mark.parametrize(
    "payload, message",
    [
        ({"from": "mysql"}, "from"),
        ({"apply": "false"}, "apply"),
        ({"threads": "pending"}, "threads"),
        ({"threads": ["pending", 3]}, "threads"),
        ({"source_url": SECRET_URL}, "POSTGRES_URL"),
        ({"dsn": "postgresql://x"}, "POSTGRES_URL"),
    ],
)
def test_invalid_payloads_are_refused_before_anything_is_read(memory, payload, message):
    owner, opener = jobs(memory)

    with pytest.raises(ValueError, match=message):
        owner.migrate(ctx(payload))
    assert opener.urls == []


def test_without_postgres_url_the_job_says_so(memory):
    owner, opener = jobs(memory, url=None)

    with pytest.raises(ValueError, match="POSTGRES_URL is not set"):
        owner.migrate(ctx())
    assert opener.urls == []


def test_errors_never_carry_the_postgres_url(memory):
    @contextmanager
    def failing(url):
        raise psycopg.OperationalError(f'invalid dsn "{url}": password s3cr3t-pa55')
        yield  # pragma: no cover

    owner = AgentMemoryJobs(
        memory, postgres_url=lambda: SECRET_URL, open_postgres=failing
    )

    with pytest.raises(RuntimeError) as raised:
        owner.migrate(ctx())
    assert "s3cr3t-pa55" not in str(raised.value)
    assert SECRET_URL not in str(raised.value)
    assert "OperationalError" in str(raised.value)
    assert raised.value.__cause__ is None and raised.value.__suppress_context__


def test_a_database_without_langgraph_tables_has_nothing_to_copy(memory):
    @contextmanager
    def no_tables(url):
        raise psycopg.errors.UndefinedTable('relation "checkpoints" does not exist')
        yield  # pragma: no cover

    owner = AgentMemoryJobs(
        memory, postgres_url=lambda: SECRET_URL, open_postgres=no_tables
    )
    context = ctx()

    report = owner.migrate(context)

    assert report["threads"] == 0
    assert any("no LangGraph checkpoints" in line for line in context.logs)


def test_a_cancelled_migration_stops_between_threads(memory, legacy):
    owner, _ = jobs(memory, legacy)
    context = ctx({"apply": True})
    context.cancelled.set()

    report = owner.migrate(context)

    assert report["threads"] == 0
    assert stored(memory) == 0
    assert any("Cancelled" in line for line in context.logs)


def test_long_thread_lists_are_cut_to_fit_the_run_record(memory, monkeypatch):
    from naas_abi_core.services.agent import AgentMemoryJobs as module

    monkeypatch.setattr(module, "MAX_LISTED", 1)
    saver = InMemorySaver()
    for name in ("a", "b", "c"):
        counting_graph().compile(checkpointer=saver).invoke({"log": []}, thread(name))
        counting_graph().compile(checkpointer=memory).invoke({"log": []}, thread(name))
    owner, _ = jobs(memory, saver)

    report = owner.migrate(ctx())

    assert report["diverged"] == ["a"]
    assert report["diverged_omitted"] == 2


def test_migrates_from_a_real_postgres_database(memory):
    from langgraph.checkpoint.postgres import PostgresSaver

    with langgraph_postgres() as url:
        with PostgresSaver.from_conn_string(url) as saver:
            approval_graph().compile(checkpointer=saver).invoke(
                {"log": ["start"]}, thread("pending")
            )
        owner = AgentMemoryJobs(memory, postgres_url=lambda: url)

        dry = owner.migrate(ctx())
        applied = owner.migrate(ctx({"apply": True}))

    assert dry["missing"] == applied["copied"] == applied["checkpoints"] > 0
    resumed = (
        approval_graph()
        .compile(checkpointer=memory)
        .invoke(Command(resume="yes"), thread("pending"))
    )
    assert resumed["log"] == ["start", "approved:yes"]


# --- agent_memory_prune ------------------------------------------------------------------


def chat(memory, thread_id, turns):
    graph = counting_graph().compile(checkpointer=memory)
    for _ in range(turns):
        graph.invoke({"log": ["turn"]}, thread(thread_id))


def test_the_scheduled_prune_keeps_the_cli_defaults(memory):
    chat(memory, "short", 2)
    owner, _ = jobs(memory)

    report = owner.prune(ctx(job="agent_memory_prune"))

    assert report["mode"] == "applied"
    assert report["keep_last"] == 20
    assert report["threads"] == 1
    assert report["checkpoints"] == 0


def test_pruning_deletes_older_checkpoints_and_keeps_the_conversation(memory):
    chat(memory, "long", 4)
    before = stored(memory)
    owner, _ = jobs(memory)
    payload = {"keep_last": 1, "min_age_seconds": 0}

    dry = owner.prune(ctx({**payload, "apply": False}, job="agent_memory_prune"))
    assert dry["mode"] == "dry-run" and dry["checkpoints"] > 0
    assert stored(memory) == before

    report = owner.prune(ctx(payload, job="agent_memory_prune"))

    assert report["checkpoints"] == dry["checkpoints"]
    assert report["pruned"][0]["thread_id"] == "long"
    assert stored(memory) == before - report["checkpoints"]
    state = counting_graph().compile(checkpointer=memory).get_state(thread("long"))
    assert state.values["log"] == ["turn", "step"] * 4


def test_pruning_only_the_selected_threads(memory):
    chat(memory, "a", 3)
    chat(memory, "b", 3)
    owner, _ = jobs(memory)

    report = owner.prune(
        ctx(
            {"threads": ["a"], "keep_last": 1, "min_age_seconds": 0},
            job="agent_memory_prune",
        )
    )

    assert report["threads"] == 1
    assert [p["thread_id"] for p in report["pruned"]] == ["a"]


def test_pruning_without_agent_memory_finds_no_thread(tmp_path):
    root = DocumentService._for_engine(
        DocumentFactory.DocumentAdapterSQLite(str(tmp_path / "empty.sqlite"))
    )
    saver = DocumentCheckpointSaver(
        root.for_namespace(ENGINE_MEMORY_NAMESPACE), agent_id=ENGINE_MEMORY_ID
    )
    owner = AgentMemoryJobs(saver, postgres_url=lambda: None)

    report = owner.prune(ctx(job="agent_memory_prune"))

    assert report["threads"] == 0
    root.adapter.close()


@pytest.mark.parametrize(
    "payload, message",
    [
        ({"keep_last": 0}, "keep_last"),
        ({"keep_last": True}, "keep_last"),
        ({"min_age_seconds": -1}, "min_age_seconds"),
        ({"apply": 1}, "apply"),
        ({"keep": 3}, "keep"),
    ],
)
def test_invalid_prune_payloads_are_refused(memory, payload, message):
    owner, _ = jobs(memory)

    with pytest.raises(ValueError, match=message):
        owner.prune(ctx(payload, job="agent_memory_prune"))


# --- wiring ------------------------------------------------------------------------------


def test_the_postgres_url_comes_from_the_secrets_then_the_environment(monkeypatch):
    monkeypatch.setenv("POSTGRES_URL", "postgresql://from-env/db")
    secrets = SimpleNamespace(
        get=lambda key, default=None: {"POSTGRES_URL": SECRET_URL}.get(key, default)
    )
    empty = SimpleNamespace(get=lambda key, default=None: default)

    assert postgres_url_from(secrets)() == SECRET_URL
    assert postgres_url_from(empty)() == "postgresql://from-env/db"
    assert postgres_url_from(None)() == "postgresql://from-env/db"
    monkeypatch.delenv("POSTGRES_URL")
    assert postgres_url_from(None)() is None


def test_the_engine_owner_reads_its_secret_service(memory, monkeypatch):
    monkeypatch.delenv("POSTGRES_URL", raising=False)
    secrets = SimpleNamespace(get=lambda key, default=None: SECRET_URL)
    services = SimpleNamespace(secret_available=lambda: True, secret=secrets)

    owner = AgentMemoryJobs.for_engine(memory, services)

    assert owner.memory is memory
    assert owner.postgres_url() == SECRET_URL
    without = AgentMemoryJobs.for_engine(
        memory, SimpleNamespace(secret_available=lambda: False)
    )
    assert without.postgres_url() is None
