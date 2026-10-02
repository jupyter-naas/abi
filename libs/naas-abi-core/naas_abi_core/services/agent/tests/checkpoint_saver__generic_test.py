"""LangGraph checkpoint saver contract, held to LangGraph's own InMemorySaver.

Subclass ``CheckpointSaverContract`` and provide a ``saver`` fixture returning
``SyncSaver(saver)`` or ``AsyncSaver(saver)``: the same scenarios then run
through the saver's synchronous or asynchronous API. ``TestInMemorySaverReference``
keeps the expectations honest: they must hold for LangGraph's reference saver.
"""

from __future__ import annotations

import asyncio
import operator
from abc import ABC
from typing import Annotated, Any, TypedDict

import pytest
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.base import ERROR, Checkpoint, empty_checkpoint
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt


class SyncSaver:
    """The contract's handle on a saver, through LangGraph's synchronous API."""

    def __init__(self, saver: Any) -> None:
        self.saver = saver

    def put(self, config, checkpoint, metadata):
        return self.saver.put(
            config, checkpoint, metadata, checkpoint["channel_versions"]
        )

    def put_writes(self, config, writes, task_id):
        self.saver.put_writes(config, writes, task_id)

    def get_tuple(self, config):
        return self.saver.get_tuple(config)

    def history(self, config, **options):
        return list(self.saver.list(config, **options))

    def delete_thread(self, thread_id):
        self.saver.delete_thread(thread_id)

    def run(self, builder, value, config):
        return builder.compile(checkpointer=self.saver).invoke(value, config)


class AsyncSaver(SyncSaver):
    """The same calls through LangGraph's asynchronous API."""

    def put(self, config, checkpoint, metadata):
        return asyncio.run(
            self.saver.aput(
                config, checkpoint, metadata, checkpoint["channel_versions"]
            )
        )

    def put_writes(self, config, writes, task_id):
        asyncio.run(self.saver.aput_writes(config, writes, task_id))

    def get_tuple(self, config):
        return asyncio.run(self.saver.aget_tuple(config))

    def history(self, config, **options):
        async def collect():
            return [item async for item in self.saver.alist(config, **options)]

        return asyncio.run(collect())

    def delete_thread(self, thread_id):
        asyncio.run(self.saver.adelete_thread(thread_id))

    def run(self, builder, value, config):
        graph = builder.compile(checkpointer=self.saver)
        return asyncio.run(graph.ainvoke(value, config))


def thread(thread_id: str, ns: str | None = "", checkpoint_id: str | None = None):
    """A config as LangGraph passes it; ``ns=None`` leaves the namespace out (list: all)."""
    configurable: dict[str, Any] = {"thread_id": thread_id}
    if ns is not None:
        configurable["checkpoint_ns"] = ns
    if checkpoint_id is not None:
        configurable["checkpoint_id"] = checkpoint_id
    return {"configurable": configurable}


_sequence = iter(range(1, 10**9))


def snapshot(*messages: Any) -> Checkpoint:
    """A checkpoint with a fresh, increasing ID and versioned channel values."""
    checkpoint = empty_checkpoint()
    checkpoint["id"] = f"1f0{next(_sequence):09d}-0000-6000-8000-000000000000"
    checkpoint["channel_values"] = {"messages": list(messages), "note": b"\x00\xff"}
    checkpoint["channel_versions"] = {"messages": 1, "note": 1}
    return checkpoint


def ids(items) -> list[str]:
    return [item.config["configurable"]["checkpoint_id"] for item in items]


def writes_by_task(item) -> dict[str, list[tuple[str, Any]]]:
    grouped: dict[str, list[tuple[str, Any]]] = {}
    for task_id, channel, value in item.pending_writes:
        grouped.setdefault(task_id, []).append((channel, value))
    return grouped


class _State(TypedDict):
    log: Annotated[list[str], operator.add]


def _approval(state: _State) -> dict[str, list[str]]:
    answer = interrupt("approve?")
    return {"log": [f"approved:{answer}"]}


def approval_graph() -> StateGraph:
    builder = StateGraph(_State)
    builder.add_node("approval", _approval)
    builder.add_edge(START, "approval")
    builder.add_edge("approval", END)
    return builder


class CheckpointSaverContract(ABC):
    def test_put_and_get_round_trip(self, saver):
        stored_checkpoint = snapshot(HumanMessage("hi", id="h1"), AIMessage("hello"))
        stored = saver.put(
            thread("t"), stored_checkpoint, {"source": "input", "step": -1}
        )
        assert stored == thread("t", "", stored_checkpoint["id"])
        for config in (thread("t"), stored):
            result = saver.get_tuple(config)
            assert result.config == stored
            assert result.checkpoint["id"] == stored_checkpoint["id"]
            assert (
                result.checkpoint["channel_values"]
                == stored_checkpoint["channel_values"]
            )
            assert result.metadata == {"source": "input", "step": -1}
            assert result.parent_config is None
            assert result.pending_writes == []

    def test_latest_checkpoint_links_to_its_parent(self, saver):
        first = saver.put(thread("t"), snapshot(), {"step": 0})
        latest_checkpoint = snapshot()
        second = saver.put(first, latest_checkpoint, {"step": 1})
        latest = saver.get_tuple(thread("t"))
        assert latest.config == second
        assert latest.parent_config == first
        assert saver.get_tuple(first).config == first

    def test_history_is_newest_first_with_before_limit_and_filter(self, saver):
        configs = [saver.put(thread("t"), snapshot(), {"source": "input", "step": 0})]
        for step in (1, 2):
            configs.append(
                saver.put(configs[-1], snapshot(), {"source": "loop", "step": step})
            )
        newest_first = ids(reversed([saver.get_tuple(c) for c in configs]))
        assert ids(saver.history(thread("t"))) == newest_first
        assert ids(saver.history(thread("t"), limit=2)) == newest_first[:2]
        assert ids(saver.history(thread("t"), before=configs[2])) == newest_first[1:]
        assert (
            ids(saver.history(thread("t"), filter={"source": "loop"}))
            == newest_first[:2]
        )
        assert (
            ids(saver.history(thread("t"), filter={"source": "loop"}, limit=1))
            == newest_first[:1]
        )
        assert ids(saver.history(configs[1])) == [newest_first[1]]
        assert saver.history(thread("t"), limit=0) == []

    def test_history_without_config_spans_threads(self, saver):
        a = saver.put(thread("a"), snapshot(), {"step": 0})
        b = saver.put(thread("b"), snapshot(), {"step": 0})
        assert set(ids(saver.history(None))) >= {
            a["configurable"]["checkpoint_id"],
            b["configurable"]["checkpoint_id"],
        }

    def test_checkpoint_namespaces_are_separate_histories(self, saver):
        root = saver.put(thread("t"), snapshot(), {"step": 0})
        child = saver.put(thread("t", "child:1"), snapshot(), {"step": 0})
        assert saver.get_tuple(thread("t")).config == root
        assert saver.get_tuple(thread("t", "child:1")).config == child
        assert ids(saver.history(thread("t"))) == [
            root["configurable"]["checkpoint_id"]
        ]
        assert set(ids(saver.history(thread("t", None)))) == {
            root["configurable"]["checkpoint_id"],
            child["configurable"]["checkpoint_id"],
        }

    def test_pending_writes_belong_to_their_checkpoint(self, saver):
        first = saver.put(thread("t"), snapshot(), {"step": 0})
        second = saver.put(first, snapshot(), {"step": 1})
        saver.put_writes(second, [("messages", "a"), ("branch", b"b")], "task-2")
        saver.put_writes(second, [("messages", AIMessage("c"))], "task-1")
        assert writes_by_task(saver.get_tuple(second)) == {
            "task-2": [("messages", "a"), ("branch", b"b")],
            "task-1": [("messages", AIMessage("c"))],
        }
        assert saver.get_tuple(first).pending_writes == []

    def test_first_task_write_wins_but_special_writes_update(self, saver):
        stored = saver.put(thread("t"), snapshot(), {"step": 0})
        saver.put_writes(stored, [("messages", "first")], "task")
        saver.put_writes(stored, [("messages", "second")], "task")
        saver.put_writes(stored, [(ERROR, "boom")], "task")
        saver.put_writes(stored, [(ERROR, "worse")], "task")
        assert dict(writes_by_task(saver.get_tuple(stored))["task"]) == {
            "messages": "first",
            ERROR: "worse",
        }

    def test_delete_thread_removes_only_that_thread(self, saver):
        doomed = saver.put(thread("doomed"), snapshot(), {"step": 0})
        saver.put_writes(doomed, [("messages", "x")], "task")
        kept = saver.put(thread("kept"), snapshot(), {"step": 0})
        saver.put_writes(kept, [("messages", "y")], "task")
        saver.delete_thread("doomed")
        assert saver.get_tuple(thread("doomed")) is None
        assert saver.history(thread("doomed")) == []
        assert saver.get_tuple(kept).pending_writes == [("task", "messages", "y")]

    def test_unknown_threads_and_checkpoints_are_absent(self, saver):
        saver.put(thread("t"), snapshot(), {"step": 0})
        assert saver.get_tuple(thread("missing")) is None
        assert saver.get_tuple(thread("t", "", "no-such-checkpoint")) is None
        assert saver.history(thread("missing")) == []

    def test_a_graph_resumes_an_interrupt_and_keeps_its_history(self, saver):
        builder, config = approval_graph(), thread("graph")
        saver.run(builder, {"log": ["start"]}, config)
        pending = saver.get_tuple(config)
        assert pending.checkpoint["channel_values"]["log"] == ["start"]
        assert pending.pending_writes  # the interrupt
        assert saver.run(builder, Command(resume="yes"), config)["log"] == [
            "start",
            "approved:yes",
        ]
        saver.run(builder, {"log": ["again"]}, config)
        assert saver.get_tuple(config).checkpoint["channel_values"]["log"] == [
            "start",
            "approved:yes",
            "again",
        ]
        assert len(saver.history(config)) >= 4


class TestInMemorySaverReference(CheckpointSaverContract):
    @pytest.fixture
    def saver(self):
        return SyncSaver(InMemorySaver())
