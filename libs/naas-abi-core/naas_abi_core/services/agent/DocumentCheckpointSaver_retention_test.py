"""Retention (``prune``) and secret redaction, on both document savers.

The same scenarios run through the engine saver (sync and async API) and the
SDK saver on one SQLite document backend, as in DocumentCheckpointSaver_test.
"""

from __future__ import annotations

import asyncio
import operator
from datetime import timedelta
from typing import Annotated, Any, TypedDict

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.types import Command, interrupt
from naas_abi_core.services.agent.DocumentCheckpointSaver_test import (
    engine_saver,
    open_root,
    sdk_saver,
)
from naas_abi_core.services.agent.tests.checkpoint_saver__generic_test import (
    AsyncSaver,
    SyncSaver,
    approval_graph,
    ids,
    thread,
)
from naas_abi_core.services.agent.tests.legacy_checkpoints import v1_saver
from naas_abi_sdk.langgraph_documents import (
    BLOBS,
    CHECKPOINTS,
    COLLECTIONS,
    ITEMS,
    LEGACY_CHECKPOINTS,
    LEGACY_WRITES,
    PARTS,
    REDACTED_SECRET,
    WRITES,
    resolution,
)
from pydantic import SecretStr

NAMESPACE = "module.agent"
NOW = timedelta(0)  # no grace period: every unreferenced document may go


@pytest.fixture
def root(tmp_path):
    service = open_root(tmp_path / "documents.sqlite")
    yield service
    service.adapter.close()


class Handle:
    """A saver driven through one API, with its prune and thread listing."""

    def __init__(self, kind: str, root) -> None:
        self.kind, self.root = kind, root
        self.raw = engine_saver(root) if kind != "sdk" else sdk_saver(root)
        self.saver = (
            SyncSaver(self.raw) if kind == "engine-sync" else AsyncSaver(self.raw)
        )

    def fresh(self) -> Handle:
        """The same store through a new saver: no remembered references."""
        return Handle(self.kind, self.root)

    def prune(self, thread_id: str, keep_last: int, *, apply=True, grace=NOW):
        if self.kind == "engine-sync":
            return self.raw.prune(
                thread_id, keep_last=keep_last, apply=apply, grace=grace
            )
        return asyncio.run(
            self.raw.aprune(thread_id, keep_last=keep_last, apply=apply, grace=grace)
        )

    def thread_ids(self) -> list[str]:
        if self.kind == "engine-sync":
            return list(self.raw.thread_ids())
        return list(asyncio.run(self.raw.athread_ids()))


@pytest.fixture(params=["engine-sync", "engine-async", "sdk"])
def handle(request, root) -> Handle:
    return Handle(request.param, root)


def chat_graph() -> StateGraph:
    def answer(state: MessagesState) -> dict[str, Any]:
        turn = len(state["messages"])
        return {"messages": [AIMessage(f"answer {turn} " + "x" * 2000, id=f"a{turn}")]}

    builder = StateGraph(MessagesState)
    builder.add_node("answer", answer)
    builder.add_edge(START, "answer")
    builder.add_edge("answer", END)
    return builder


def chat(handle: Handle, thread_id: str, turns: int, start: int = 0) -> None:
    for turn in range(start, start + turns):
        handle.saver.run(
            chat_graph(),
            {
                "messages": [
                    HumanMessage(f"question {turn} " + "q" * 1500, id=f"h{turn}")
                ]
            },
            thread(thread_id),
        )


def documents(root) -> dict[str, dict[str, dict[str, Any]]]:
    view = root.for_namespace(NAMESPACE)
    found: dict[str, dict[str, dict[str, Any]]] = {}
    for collection in (*COLLECTIONS, LEGACY_CHECKPOINTS, LEGACY_WRITES):
        try:
            found[collection] = {d.id: d.data for d in view.iterate(collection)}
        except Exception:  # noqa: BLE001 - a collection never created
            found[collection] = {}
    return found


def referenced(stored) -> set[str]:
    """Every value document the stored checkpoints and writes reference."""
    by_ref = {
        data["ref"]: data for c in (BLOBS, ITEMS, PARTS) for data in stored[c].values()
    }
    flow = resolution([*stored[CHECKPOINTS].values(), *stored[WRITES].values()])
    try:
        _, refs = next(flow)
        while True:
            _, refs = flow.send([by_ref[r] for r in refs])
    except StopIteration as done:
        return set(done.value)


def values(stored) -> set[str]:
    return {data["ref"] for c in (BLOBS, ITEMS, PARTS) for data in stored[c].values()}


# --- retention ---------------------------------------------------------------------------


def test_prune_keeps_the_newest_checkpoints_and_the_thread_continues(handle):
    chat(handle, "t", turns=6)
    before = handle.saver.history(thread("t"))
    head = handle.saver.get_tuple(thread("t"))

    report = handle.prune("t", keep_last=2)

    assert ids(handle.saver.history(thread("t"))) == ids(before)[:2]
    assert (report.kept, report.checkpoints) == (2, len(before) - 2)
    assert report.values > 0 and report.applied
    assert handle.saver.get_tuple(before[-1].config) is None
    latest = handle.fresh().saver.get_tuple(thread("t"))
    assert latest.checkpoint["channel_values"] == head.checkpoint["channel_values"]
    chat(handle, "t", turns=1, start=6)
    chat(handle.fresh(), "t", turns=1, start=7)
    messages = handle.fresh().saver.get_tuple(thread("t")).checkpoint["channel_values"]
    assert [m.id for m in messages["messages"]][-4:] == ["h6", "a13", "h7", "a15"]
    assert len(messages["messages"]) == 16


def test_prune_deletes_exactly_what_no_kept_checkpoint_references(handle, root):
    chat(handle, "t", turns=5)
    before = documents(root)

    handle.prune("t", keep_last=1)

    after = documents(root)
    assert values(after) == referenced(after)  # nothing dangling, nothing missing
    assert values(after) < values(before)
    assert len(after[CHECKPOINTS]) == 1


def test_a_dry_run_reports_without_deleting(handle, root):
    chat(handle, "t", turns=4)
    before = documents(root)

    dry = handle.prune("t", keep_last=1, apply=False)

    assert documents(root) == before
    applied = handle.prune("t", keep_last=1)
    assert not dry.applied and applied.applied
    assert (dry.kept, dry.checkpoints, dry.writes, dry.values) == (
        applied.kept,
        applied.checkpoints,
        applied.writes,
        applied.values,
    )
    again = handle.prune("t", keep_last=1)
    assert (again.checkpoints, again.writes, again.values) == (0, 0, 0)


def test_recent_values_are_kept_within_the_grace_period(handle, root):
    chat(handle, "t", turns=4)
    stored = values(documents(root))

    report = handle.prune("t", keep_last=1, grace=timedelta(minutes=5))

    assert report.checkpoints > 0 and report.values == 0
    assert values(documents(root)) == stored
    assert handle.fresh().saver.get_tuple(thread("t")) is not None


def test_prune_leaves_other_threads_alone(handle, root):
    chat(handle, "t", turns=3)
    chat(handle, "other", turns=3)
    other = handle.saver.history(thread("other"))

    handle.prune("t", keep_last=1)

    assert ids(handle.saver.history(thread("other"))) == ids(other)
    assert handle.fresh().saver.get_tuple(thread("other")) is not None
    assert sorted(handle.thread_ids()) == ["other", "t"]


def test_an_interrupted_graph_still_resumes_after_pruning(handle):
    builder, config = approval_graph(), thread("graph")
    handle.saver.run(builder, {"log": ["one"]}, config)
    handle.saver.run(builder, Command(resume="first"), config)
    handle.saver.run(builder, {"log": ["two"]}, config)  # interrupted again

    handle.prune("graph", keep_last=1)

    resumed = handle.fresh().saver.run(builder, Command(resume="second"), config)
    assert resumed["log"] == ["one", "approved:first", "two", "approved:second"]


class _Inner(TypedDict):
    log: Annotated[list[str], operator.add]


def subgraph_graph(*, ask: bool) -> StateGraph:
    def step(state: _Inner) -> dict[str, list[str]]:
        if ask:
            return {"log": [f"answer:{interrupt('approve?')}"]}
        return {"log": ["inner"]}

    inner = StateGraph(_Inner)
    inner.add_node("step", step)
    inner.add_edge(START, "step")
    inner.add_edge("step", END)
    outer = StateGraph(_Inner)
    outer.add_node("sub", inner.compile())
    outer.add_edge(START, "sub")
    outer.add_edge("sub", END)
    return outer


def namespaces(handle: Handle, thread_id: str) -> set[str]:
    history = handle.saver.history(thread(thread_id, ns=None))
    return {item.config["configurable"]["checkpoint_ns"] for item in history}


def test_subgraph_steps_go_with_the_root_checkpoint_they_ran_under(handle):
    for turn in range(3):
        handle.saver.run(
            subgraph_graph(ask=False), {"log": [f"turn {turn}"]}, thread("s")
        )
    assert len(namespaces(handle, "s") - {""}) == 3  # one per subgraph task

    handle.prune("s", keep_last=2)
    # The newest root checkpoint is after the last subgraph run; the one before
    # it is the checkpoint that run started from.
    assert len(namespaces(handle, "s") - {""}) == 1

    handle.prune("s", keep_last=1)
    assert namespaces(handle, "s") == {""}
    assert handle.fresh().saver.get_tuple(thread("s")) is not None


def test_an_interrupted_subgraph_still_resumes_after_pruning(handle):
    graph, config = subgraph_graph(ask=True), thread("s")
    steps = [{"log": ["one"]}, Command(resume="yes"), {"log": ["two"]}]
    for step in steps:  # the last one is interrupted inside the subgraph
        handle.saver.run(graph, step, config)

    handle.prune("s", keep_last=1)

    assert len(namespaces(handle, "s") - {""}) == 1
    resumed = handle.fresh().saver.run(graph, Command(resume="ok"), config)
    reference = SyncSaver(InMemorySaver())  # the same steps, nothing pruned
    for step in [*steps, Command(resume="ok")]:
        expected = reference.run(graph, step, config)
    assert resumed == expected and "answer:ok" in resumed["log"]


def test_schema_1_history_is_pruned_too(handle, root):
    builder, config = approval_graph(), thread("legacy")
    legacy = v1_saver(root.for_namespace(NAMESPACE), "agent")
    builder.compile(checkpointer=legacy).invoke({"log": ["start"]}, config)
    handle.saver.run(builder, Command(resume="ok"), config)
    assert documents(root)[LEGACY_CHECKPOINTS]

    report = handle.prune("legacy", keep_last=1)

    stored = documents(root)
    assert stored[LEGACY_CHECKPOINTS] == {} and stored[LEGACY_WRITES] == {}
    assert report.kept == 1 and len(stored[CHECKPOINTS]) == 1
    assert handle.thread_ids() == ["legacy"]
    head = handle.fresh().saver.get_tuple(config)
    assert head.checkpoint["channel_values"]["log"] == ["start", "approved:ok"]


def test_keep_last_must_keep_something(handle):
    with pytest.raises(ValueError, match="keep_last"):
        handle.prune("t", keep_last=0)


# --- secrets -----------------------------------------------------------------------------


class _Vault(TypedDict):
    log: Annotated[list[str], operator.add]
    credentials: SecretStr


def test_secrets_in_state_are_never_stored(handle, root):
    secret = "hunter2-never-in-a-document"

    def use(state: _Vault) -> dict[str, Any]:
        return {"log": [f"used {len(state['credentials'].get_secret_value())} chars"]}

    builder = StateGraph(_Vault)
    builder.add_node("use", use)
    builder.add_edge(START, "use")
    builder.add_edge("use", END)

    result = handle.saver.run(
        builder, {"log": ["start"], "credentials": SecretStr(secret)}, thread("v")
    )

    assert result["log"] == ["start", f"used {len(secret)} chars"]  # the run had it
    assert secret.encode() not in repr(documents(root)).encode()
    stored = handle.fresh().saver.get_tuple(thread("v")).checkpoint["channel_values"]
    assert stored["credentials"].get_secret_value() == REDACTED_SECRET


def test_the_schema_1_reader_never_prunes(root):
    from naas_abi_core.services.agent.DocumentCheckpointSaver import (
        LegacyDocumentCheckpointReader,
    )

    reader = LegacyDocumentCheckpointReader(
        root.for_namespace(NAMESPACE), agent_id="agent"
    )
    with pytest.raises(NotImplementedError):
        reader.prune("t", keep_last=1)
