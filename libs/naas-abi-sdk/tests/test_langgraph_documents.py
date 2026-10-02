"""The checkpoint document schema both LangGraph savers (SDK and core) write."""

import pytest

pytest.importorskip("langgraph.checkpoint.base")

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.base import ERROR, empty_checkpoint
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer

from naas_abi_sdk.langgraph_documents import (
    BLOBS,
    CHECKPOINTS,
    COLLECTIONS,
    ITEMS,
    PART_SIZE,
    PARTS,
    READ_BUDGET,
    WRITES,
    CheckpointDocuments,
    Known,
    KnownReferences,
    batches,
    next_version,
    raw_channel_values,
    resolution,
)

ROOT = {"configurable": {"thread_id": "t-1", "checkpoint_ns": ""}}


@pytest.fixture
def schema():
    return CheckpointDocuments("agent-a", JsonPlusSerializer())


def snapshot(checkpoint_id, **values):
    checkpoint = empty_checkpoint()
    checkpoint["id"] = checkpoint_id
    checkpoint["channel_values"] = values
    checkpoint["channel_versions"] = {name: 1 for name in values}
    return checkpoint


def conversation(turns):
    messages = []
    for turn in range(turns):
        messages += [
            HumanMessage(f"question {turn} " + "q" * 300, id=f"h{turn}"),
            AIMessage(f"answer {turn} " + "a" * 300, id=f"a{turn}"),
        ]
    return messages


def stored(plan):
    """Every planned document by ref (or by key for checkpoints and writes)."""
    return {p.data.get("ref", p.key): p.data for p in plan.puts}


def restore(schema, plan, documents):
    """Run the read side over ``documents``, as a saver driving the resolution."""
    checkpoint = plan.puts[-1].data
    flow = resolution([checkpoint])
    try:
        request = next(flow)
        while True:
            _, refs = request
            assert all(len(r) > 2 for r in refs)
            request = flow.send([documents[r] for r in refs if r in documents])
    except StopIteration as done:
        fetched = done.value
    return schema.restore(checkpoint, [], fetched), fetched


def test_collections_and_indexed_fields_are_the_stored_contract():
    assert COLLECTIONS == {
        "langgraph_checkpoints_v2": (
            "agent_id",
            "thread_id",
            "checkpoint_ns",
            "checkpoint_id",
        ),
        "langgraph_writes_v2": (
            "agent_id",
            "thread_id",
            "checkpoint_ns",
            "checkpoint_id",
        ),
        "langgraph_blobs_v2": ("agent_id", "thread_id", "ref"),
        "langgraph_items_v2": ("agent_id", "thread_id", "ref"),
        "langgraph_parts_v2": ("agent_id", "thread_id", "ref"),
    }


def test_requires_a_stable_agent_identity():
    with pytest.raises(ValueError, match="agent_id"):
        CheckpointDocuments("", JsonPlusSerializer())


def test_checkpoint_and_write_ids_never_change(schema):
    plan = schema.checkpoint_plan(
        ROOT, snapshot("c-1"), {"source": "input", "step": -1}
    )
    # Stored documents are addressed by these ids: changing them orphans every thread.
    assert (
        plan.puts[-1].key
        == "e983edcf00b13ed7725bc6704e320e3a169809587086e7166d4cd9441cad31cd"
    )
    write = schema.write_plan(plan.config, [("messages", "hello")], "task-1")[0]
    assert (
        write.key == "43b6f2b667744a779b04f40884401d34c1b35103703c99acd4dff264c18489f8"
    )
    assert plan.puts[-1].data["_schema"] == 2


def test_small_values_stay_in_the_checkpoint_document(schema):
    plan = schema.checkpoint_plan(
        ROOT, snapshot("c-1", active="Researcher", step=3), {}
    )
    assert [p.collection for p in plan.puts] == [CHECKPOINTS]
    channels = plan.puts[-1].data["channels"]
    assert schema.load(channels["active"]["value"]) == "Researcher"


def test_a_conversation_is_stored_once_and_each_step_adds_only_what_is_new(schema):
    first = schema.checkpoint_plan(ROOT, snapshot("c-1", messages=conversation(20)), {})
    assert {p.collection for p in first.puts} == {ITEMS, BLOBS, CHECKPOINTS}
    schema.known.remember(*first.remember)

    grown = snapshot(
        "c-2", messages=[*conversation(20), HumanMessage("one more", id="n")]
    )
    grown["channel_versions"] = {"messages": 2}
    child = schema.checkpoint_plan(first.config, grown, {})
    elements = [p for p in child.puts if p.data.get("ref", "").startswith("e-")]
    chunks = [p for p in child.puts if p.data.get("ref", "").startswith("c-")]
    assert len(elements) == 1  # the new message only
    assert len(chunks) == 1  # the last chunk only
    assert (
        sum(len(str(p.data)) for p in child.puts)
        < sum(len(str(p.data)) for p in first.puts) / 10
    )


def test_an_unchanged_channel_is_reused_without_serializing_it(schema):
    class Opaque:
        """A value the serializer would only see if the channel were rewritten."""

    first = schema.checkpoint_plan(ROOT, snapshot("c-1", messages=conversation(5)), {})
    schema.known.remember(*first.remember)
    child = snapshot("c-2", messages=Opaque())
    child["channel_versions"] = {"messages": 1}
    plan = schema.checkpoint_plan(first.config, child, {})
    assert [p.collection for p in plan.puts] == [CHECKPOINTS]
    assert plan.puts[-1].data["channels"] == first.puts[-1].data["channels"]


def test_any_value_is_split_into_parts_and_restored(schema):
    huge = "x" * (3 * PART_SIZE + 17)
    plan = schema.checkpoint_plan(
        ROOT,
        snapshot("c-1", messages=[HumanMessage("hi", id="h"), AIMessage(huge, id="a")]),
        {},
    )
    parts = [p for p in plan.puts if p.collection == PARTS]
    assert len(parts) == 4
    assert all(len(p.data["payload"]) <= PART_SIZE for p in parts)
    restored, fetched = restore(schema, plan, stored(plan))
    assert restored.checkpoint["channel_values"]["messages"][1].content == huge
    assert set(fetched) == {p.data["ref"] for p in plan.puts if "ref" in p.data}


def test_reads_are_planned_in_batches_within_the_read_budget():
    refs = [(f"e-{i:064x}", 200_000) for i in range(30)] + [
        (f"p-{i}.0", PART_SIZE) for i in range(9)
    ]
    planned = batches(refs)
    for collection, batch in planned:
        sizes = dict(refs)
        assert sum(sizes[r] for r in batch) <= READ_BUDGET or len(batch) == 1
    assert sorted(r for _, b in planned for r in b) == sorted(r for r, _ in refs)
    assert {c for c, _ in planned} == {ITEMS, PARTS}


def test_raw_values_are_typed_bytes_never_deserialized(schema):
    plan = schema.checkpoint_plan(
        ROOT, snapshot("c-1", messages=conversation(3), note="n"), {}
    )
    documents = stored(plan)
    _, fetched = restore(schema, plan, documents)
    raw = raw_channel_values(plan.puts[-1].data, fetched)
    assert [item["kind"] for item in raw["messages"]] == ["msgpack"] * 6
    assert all(isinstance(item["payload"], bytes) for item in raw["messages"])
    assert schema.load(raw["note"]) == "n"


def test_missing_documents_are_an_error_not_a_shorter_history(schema):
    plan = schema.checkpoint_plan(ROOT, snapshot("c-1", messages=conversation(5)), {})
    documents = {k: v for k, v in stored(plan).items() if not k.startswith("e-")}
    with pytest.raises(ValueError, match="missing"):
        restore(schema, plan, documents)


def test_writes_are_first_write_wins_except_special_channels(schema):
    config = {
        "configurable": {
            "thread_id": "t-1",
            "checkpoint_ns": "",
            "checkpoint_id": "c-1",
        }
    }
    puts = schema.write_plan(
        config, [("messages", "x" * (PART_SIZE + 1)), (ERROR, "boom")], "t", "p"
    )
    assert [p.collection for p in puts] == [PARTS, PARTS, WRITES, WRITES]
    ordinary, special = puts[2], puts[3]
    assert (ordinary.data["index"], ordinary.if_version, ordinary.on_conflict) == (
        0,
        0,
        "keep",
    )
    assert special.data["index"] < 0 and special.if_version is None
    assert ordinary.data["task_path"] == "p"


def test_schema_1_documents_are_still_read(schema):
    serde = JsonPlusSerializer()
    checkpoint = snapshot("c-1", messages=conversation(1))
    kind, payload = serde.dumps_typed(checkpoint)
    legacy = {
        "agent_id": "agent-a",
        "thread_id": "t-1",
        "checkpoint_ns": "",
        "checkpoint_id": "c-1",
        "_schema": 1,
        "parent_id": None,
        "checkpoint": {"kind": kind, "payload": payload},
        "metadata": dict(zip(("kind", "payload"), serde.dumps_typed({"step": 1}))),
    }
    write = {
        "task_id": "t",
        "index": 0,
        "channel": "messages",
        "value": dict(zip(("kind", "payload"), serde.dumps_typed("w"))),
    }
    restored = schema.restore(legacy, [write], {})
    assert restored.checkpoint["channel_values"] == checkpoint["channel_values"]
    assert restored.metadata == {"step": 1}
    assert restored.pending_writes == [("t", "messages", "w")]


def test_known_references_are_bounded():
    known = KnownReferences(capacity=10)
    for index in range(5):
        known.remember(
            ("t", "", f"c{index}"),
            Known(frozenset(f"r{index}-{i}" for i in range(4)), {}),
        )
    assert known.recall("t", ("", "c0"), []).refs == frozenset()  # evicted
    assert known.recall("t", ("", "c4"), []).refs == {f"r4-{i}" for i in range(4)}
    known.forget("t")
    assert known.recall("t", ("", "c4"), []).refs == frozenset()


@pytest.mark.parametrize(
    ("current", "expected_type"),
    [(None, int), (1, int), ("00000000000000000000000000000001.5", str)],
)
def test_next_version_keeps_the_thread_version_type(current, expected_type):
    # Threads migrated from LangGraph's PostgreSQL saver carry string versions.
    following = next_version(current)
    assert type(following) is expected_type
    if current is not None:
        assert following > current
