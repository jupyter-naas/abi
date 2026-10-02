"""The engine's document checkpointer, and its compatibility with the SDK saver.

Both savers share one SQLite document backend here. The SDK saver reaches it
through the real document RPC handler, called in-process instead of over NATS.
"""

from __future__ import annotations

import asyncio
import operator
import threading
import time
from typing import Annotated, TypedDict

import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.base import ERROR
from langgraph.graph import END, START, MessagesState, StateGraph
from langgraph.types import Command
from naas_abi_core.services.agent.DocumentCheckpointSaver import (
    ENGINE_MEMORY_ID,
    ENGINE_MEMORY_NAMESPACE,
    DocumentCheckpointSaver,
)
from naas_abi_core.services.agent.tests.checkpoint_saver__generic_test import (
    AsyncSaver,
    CheckpointSaverContract,
    SyncSaver,
    approval_graph,
    snapshot,
    thread,
)
from naas_abi_core.services.agent.tests.legacy_checkpoints import v1_saver
from naas_abi_core.services.document.adapters.document_nats_codec import ERRORS
from naas_abi_core.services.document.adapters.primary.document__primary_adapter__NATS import (
    DocumentPrimaryAdapterNATS,
)
from naas_abi_core.services.document.DocumentFactory import DocumentFactory
from naas_abi_core.services.document.DocumentPort import VersionConflict
from naas_abi_core.services.document.DocumentService import DocumentService
from naas_abi_proto.document.values import encode_data
from naas_abi_sdk.document import DocumentClient
from naas_abi_sdk.langgraph import DocumentCheckpointSaver as SDKCheckpointSaver
from naas_abi_sdk.langgraph_documents import (
    BLOBS,
    CHECKPOINTS,
    COLLECTIONS,
    ITEMS,
    LEGACY_CHECKPOINTS,
    LEGACY_WRITES,
    PART_SIZE,
    PARTS,
    READ_BUDGET,
    WRITES,
)
from naas_abi_sdk.transport import RPCError


class InProcessTransport:
    """The SDK transport contract, served by the document RPC handler in-process.

    Requests and replies above ``max_payload`` fail, as on a broker.
    """

    def __init__(
        self, root: DocumentService, max_payload: int = 8 * 1024 * 1024
    ) -> None:
        self.server = DocumentPrimaryAdapterNATS(root, "s" * 32)
        self.max_payload = max_payload
        self.largest = 0

    def _check(self, message) -> None:
        size = message.ByteSize()
        self.largest = max(self.largest, size)
        if size > self.max_payload:
            raise RPCError("MAX_PAYLOAD", f"{size} bytes")

    async def call(self, subject, request, response_type):
        self._check(request)
        try:
            response = self.server._call(subject.rsplit(".", 1)[1], request)
        except Exception as exc:
            code = next(
                (code for code, cls in ERRORS.items() if isinstance(exc, cls)),
                "INTERNAL",
            )
            raise RPCError(code, code) from exc
        self._check(response)
        return response


def open_root(path) -> DocumentService:
    return DocumentService._for_engine(DocumentFactory.DocumentAdapterSQLite(str(path)))


@pytest.fixture
def root(tmp_path):
    service = open_root(tmp_path / "documents.sqlite")
    yield service
    service.adapter.close()


def engine_saver(root, namespace="module.agent", agent_id="agent"):
    saver = DocumentCheckpointSaver(root.for_namespace(namespace), agent_id=agent_id)
    saver.setup()
    return saver


def sdk_saver(root, namespace="module.agent", agent_id="agent", max_payload=8 << 20):
    transport = InProcessTransport(root, max_payload)
    client = DocumentClient(transport, namespace)  # type: ignore[arg-type]
    saver = SDKCheckpointSaver(client, agent_id=agent_id)
    asyncio.run(saver.setup())
    saver.transport = transport  # type: ignore[attr-defined]
    return saver


class TestEngineSaverSync(CheckpointSaverContract):
    @pytest.fixture
    def saver(self, root):
        return SyncSaver(engine_saver(root))


class TestEngineSaverAsync(CheckpointSaverContract):
    @pytest.fixture
    def saver(self, root):
        return AsyncSaver(engine_saver(root))


class TestSDKSaverOnTheSameBackend(CheckpointSaverContract):
    @pytest.fixture
    def saver(self, root):
        return AsyncSaver(sdk_saver(root))


def stored_documents(root, namespace):
    documents = root.for_namespace(namespace)
    return {
        collection: {d.id: d.data for d in documents.iterate(collection)}
        for collection in COLLECTIONS
    }


def test_both_savers_write_identical_documents(root):
    long = [
        HumanMessage("question " * 200, id="h"),
        AIMessage("x" * (PART_SIZE + 9), id="a"),
    ]
    checkpoint = snapshot(*long)
    child = snapshot(*long, AIMessage("more", id="m"))
    child["channel_versions"] = {"messages": 2, "note": 1}
    for saver in (
        SyncSaver(engine_saver(root, "engine.side")),
        AsyncSaver(sdk_saver(root, "sdk.side")),
    ):
        first = saver.put(thread("t"), checkpoint, {"source": "input", "step": -1})
        second = saver.put(first, child, {"source": "loop", "step": 0})
        saver.put_writes(second, [("messages", "a"), (ERROR, "boom")], "task")
    engine_side = stored_documents(root, "engine.side")
    assert engine_side == stored_documents(root, "sdk.side")
    assert {c: len(d) for c, d in engine_side.items()} == {
        CHECKPOINTS: 2,
        WRITES: 2,
        BLOBS: 2,  # one per version of the list
        ITEMS: 5,  # three messages, two versions of the one chunk
        PARTS: 2,  # the large message, stored once
    }


def test_a_thread_moves_between_engine_and_sdk_savers(root):
    builder, config = approval_graph(), thread("conversation")
    engine, sdk = SyncSaver(engine_saver(root)), AsyncSaver(sdk_saver(root))
    engine.run(builder, {"log": ["start"]}, config)
    assert sdk.run(builder, Command(resume="yes"), config)["log"] == [
        "start",
        "approved:yes",
    ]
    engine.run(builder, {"log": ["engine again"]}, config)
    assert sdk.get_tuple(config).checkpoint["channel_values"]["log"] == [
        "start",
        "approved:yes",
        "engine again",
    ]


def test_namespace_agent_and_thread_isolate_state(root):
    owner = SyncSaver(engine_saver(root, "module.a", "agent-x"))
    stored = owner.put(thread("t"), snapshot(), {"step": 0})
    owner.put_writes(stored, [("messages", "x")], "task")
    for other in (
        SyncSaver(engine_saver(root, "module.b", "agent-x")),
        SyncSaver(engine_saver(root, "module.a", "agent-y")),
        AsyncSaver(sdk_saver(root, "module.b", "agent-x")),
    ):
        assert other.get_tuple(thread("t")) is None
        assert other.history(None) == []
        other.delete_thread("t")
    assert owner.get_tuple(thread("t")).pending_writes == [("task", "messages", "x")]
    assert owner.get_tuple(thread("other")) is None


def test_a_checkpoint_id_is_never_overwritten_with_different_state(root):
    engine, sdk = engine_saver(root), sdk_saver(root)
    checkpoint = snapshot()
    stored = engine.put(thread("t"), checkpoint, {"step": 0}, {})
    # An identical repeat (a retried call) is accepted by either saver.
    assert engine.put(thread("t"), checkpoint, {"step": 0}, {}) == stored
    assert asyncio.run(sdk.aput(thread("t"), checkpoint, {"step": 0}, {})) == stored
    divergent = dict(checkpoint, channel_values={"messages": ["other"]})
    with pytest.raises(VersionConflict):
        engine.put(thread("t"), divergent, {"step": 0}, {})  # type: ignore[arg-type]
    with pytest.raises(RPCError, match="VERSION_CONFLICT"):
        asyncio.run(sdk.aput(thread("t"), divergent, {"step": 0}, {}))  # type: ignore[arg-type]
    assert (
        engine.get_tuple(stored).checkpoint["channel_values"]
        == checkpoint["channel_values"]
    )


def test_memory_survives_a_restart(tmp_path):
    builder, config = approval_graph(), thread("conversation")
    before = open_root(tmp_path / "documents.sqlite")
    SyncSaver(engine_saver(before)).run(builder, {"log": ["start"]}, config)
    before.adapter.close()

    after = open_root(tmp_path / "documents.sqlite")
    resumed = SyncSaver(engine_saver(after)).run(builder, Command(resume="ok"), config)
    assert resumed["log"] == ["start", "approved:ok"]
    after.adapter.close()


def test_engine_scope_is_one_shared_namespace_and_agent_id(root):
    saver = DocumentCheckpointSaver.for_engine(root)
    assert saver.documents.namespace == ENGINE_MEMORY_NAMESPACE
    assert saver.agent_id == ENGINE_MEMORY_ID
    assert set(saver.documents.collections()) == set(COLLECTIONS)
    DocumentCheckpointSaver.for_engine(root)  # setup is idempotent


def test_threads_migrated_from_postgres_keep_string_versions(root):
    saver = engine_saver(root)
    assert saver.get_next_version(None, None) == 1
    assert saver.get_next_version(1, None) == 2
    migrated = "00000000000000000000000000000007.123"
    assert saver.get_next_version(migrated, None) > migrated


class _Turn(TypedDict):
    log: Annotated[list[str], operator.add]


def test_concurrent_turns_on_one_thread_fork_without_corruption(root):
    """Two overlapping turns (two browser tabs) on one thread.

    As with LangGraph's PostgreSQL saver, both start from the same parent and the
    later checkpoint becomes the head; no document is overwritten or torn.
    """
    started = threading.Barrier(2)

    def slow(state):
        if state["log"][-1] != "first":  # only the two tabs overlap
            started.wait(timeout=5)
            time.sleep(0.05)
        return {"log": ["done"]}

    builder = StateGraph(_Turn)
    builder.add_node("slow", slow)
    builder.add_edge(START, "slow")
    builder.add_edge("slow", END)
    saver = engine_saver(root)
    graph = builder.compile(checkpointer=saver)
    config = thread("tabs")
    graph.invoke({"log": ["first"]}, config)

    errors = []

    def turn(text):
        try:
            graph.invoke({"log": [text]}, config)
        except BaseException as exc:  # noqa: BLE001 - surfaced by the assertion below
            errors.append(exc)

    tabs = [threading.Thread(target=turn, args=(t,)) for t in ("tab-a", "tab-b")]
    for tab in tabs:
        tab.start()
    for tab in tabs:
        tab.join(timeout=10)
    assert errors == []
    history = list(saver.list(config))
    stored = {item.config["configurable"]["checkpoint_id"] for item in history}
    assert all(
        item.parent_config["configurable"]["checkpoint_id"] in stored
        for item in history
        if item.parent_config
    )
    head = saver.get_tuple(config).checkpoint["channel_values"]["log"]
    assert head in (
        ["first", "done", "tab-a", "done"],
        ["first", "done", "tab-b", "done"],
    )


# --- schema 2: increments, legacy threads, size bounds ---------------------------------


@pytest.mark.parametrize("runtime", ["engine", "sdk"])
def test_schema_1_threads_are_read_and_continue_in_schema_2(root, runtime):
    builder, config = approval_graph(), thread("legacy")
    legacy = v1_saver(root.for_namespace("module.agent"), "agent")
    builder.compile(checkpointer=legacy).invoke({"log": ["start"]}, config)
    old_history = len(list(legacy.list(config)))

    saver = (
        SyncSaver(engine_saver(root))
        if runtime == "engine"
        else AsyncSaver(sdk_saver(root))
    )
    assert saver.get_tuple(config).checkpoint["channel_values"]["log"] == ["start"]
    assert saver.run(builder, Command(resume="ok"), config)["log"] == [
        "start",
        "approved:ok",
    ]
    history = saver.history(config)
    assert len(history) > old_history  # schema 2 steps, then the schema 1 ones
    assert (
        root.for_namespace("module.agent").count(CHECKPOINTS)
        == len(history) - old_history
    )
    assert (
        saver.get_tuple(history[-1].config) is not None
    )  # a schema 1 checkpoint by id
    saver.delete_thread("legacy")
    assert saver.get_tuple(config) is None
    for collection in (LEGACY_CHECKPOINTS, LEGACY_WRITES, *COLLECTIONS):
        assert root.for_namespace("module.agent").count(collection) == 0


def test_a_value_far_above_the_broker_limit_round_trips(root):
    """A 20 MB tool result; no request or reply exceeds the read budget."""
    cap = READ_BUDGET + 64 * 1024  # protobuf framing
    huge = "r" * (20 * 1024 * 1024)

    def tool_result(state):
        return {"messages": [ToolMessage(huge, tool_call_id="call-1")]}

    builder = StateGraph(MessagesState)
    builder.add_node("tool", tool_result)
    builder.add_edge(START, "tool")
    builder.add_edge("tool", END)
    sdk = sdk_saver(root, max_payload=cap)
    config = thread("big")
    AsyncSaver(sdk).run(builder, {"messages": [HumanMessage("fetch it")]}, config)
    restored = AsyncSaver(sdk_saver(root, max_payload=cap)).get_tuple(config)
    assert restored.checkpoint["channel_values"]["messages"][-1].content == huge
    assert sdk.transport.largest <= cap
    engine = SyncSaver(engine_saver(root))
    assert (
        engine.get_tuple(config).checkpoint["channel_values"]["messages"][-1].content
        == huge
    )


class CountingAdapter:
    """A document adapter that records the wire size of every document written."""

    def __init__(self, inner) -> None:
        self.inner = inner
        self.written: list[int] = []

    def __getattr__(self, name):
        return getattr(self.inner, name)

    def put(self, namespace, collection, id, data, if_version):
        self.written.append(encode_data(data).ByteSize())
        return self.inner.put(namespace, collection, id, data, if_version)


def bytes_per_turn(saver_kind, tmp_path, turns=30) -> list[int]:
    from naas_abi_core.engine.context import with_agent_checkpointer_override
    from naas_abi_core.services.agent.Agent import (
        Agent,
        AgentConfiguration,
        AgentSharedState,
    )
    from naas_abi_core.services.agent.Agent_document_memory_test import Scripted

    counter = CountingAdapter(
        DocumentFactory.DocumentAdapterSQLite(str(tmp_path / "d.sqlite"))
    )
    root = DocumentService._for_engine(counter)  # type: ignore[arg-type]
    saver = engine_saver(root) if saver_kind == "engine" else sdk_saver(root)
    replies = [AIMessage(f"answer {t} " + "a" * 800) for t in range(turns)]
    with with_agent_checkpointer_override(saver):
        template = Agent(
            name="Chat",
            description="Chats.",
            chat_model=Scripted(replies=replies),
            configuration=AgentConfiguration(
                system_prompt="You are Chat. " + "rule " * 300
            ),
        )
    sizes = []
    for turn in range(turns):
        before = len(counter.written)
        agent = template.duplicate(
            agent_shared_state=AgentSharedState(thread_id="chat")
        )
        prompt = f"question {turn} " + "q" * 200
        if saver_kind == "engine":
            agent.invoke(prompt)
        else:  # the SDK saver is async-only
            asyncio.run(
                agent.graph.ainvoke(
                    {"messages": [HumanMessage(prompt)]},
                    {"configurable": {"thread_id": "chat"}},
                )
            )
        sizes.append(sum(counter.written[before:]))
    assert max(counter.written) <= PART_SIZE + 4096
    return sizes


@pytest.mark.parametrize("saver_kind", ["engine", "sdk"])
def test_each_turn_writes_what_is_new_not_the_history(
    saver_kind, tmp_path, monkeypatch
):
    monkeypatch.delenv("ENV", raising=False)
    sizes = bytes_per_turn(saver_kind, tmp_path)
    early, late = sum(sizes[5:10]) / 5, sum(sizes[25:30]) / 5
    # Schema 1 grew from 20 KB to 268 KB per turn over this conversation.
    assert late <= 1.3 * early, sizes
