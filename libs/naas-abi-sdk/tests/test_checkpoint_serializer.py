"""Checkpoint values decode as data: only value classes are rebuilt."""

from __future__ import annotations

import datetime
import decimal
import enum
import json
import uuid

import pytest

# The checkpoint serializer comes with the langgraph extra.
pytest.importorskip("langgraph.checkpoint.serde.jsonplus")

import ormsgpack  # noqa: E402
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage  # noqa: E402
from langgraph.checkpoint.serde.jsonplus import (  # noqa: E402
    EXT_CONSTRUCTOR_KW_ARGS,
    EXT_CONSTRUCTOR_POS_ARGS,
    EXT_CONSTRUCTOR_SINGLE_ARG,
    EXT_METHOD_SINGLE_ARG,
    EXT_PYDANTIC_V2,
)
from pydantic import SecretStr  # noqa: E402

from naas_abi_sdk.langgraph_documents import (  # noqa: E402
    CheckpointDocuments,
    CheckpointSerializer,
    checkpoint_serde,
)

CALLS: list[object] = []


def record(value: object) -> str:
    """A function a stored value might name: it must never be called."""
    CALLS.append(value)
    return "called"


class Colour(enum.Enum):
    RED = "red"


def _ext(code: int, *fields: object) -> bytes:
    return ormsgpack.packb(ormsgpack.Ext(code, ormsgpack.packb(list(fields))))


@pytest.fixture(autouse=True)
def _no_calls():
    CALLS.clear()
    yield
    assert CALLS == []


@pytest.mark.parametrize(
    "payload",
    [
        _ext(EXT_CONSTRUCTOR_SINGLE_ARG, __name__, "record", "single"),
        _ext(EXT_CONSTRUCTOR_POS_ARGS, __name__, "record", ["positional"]),
        _ext(EXT_CONSTRUCTOR_KW_ARGS, __name__, "record", {"value": "kw"}),
        _ext(EXT_METHOD_SINGLE_ARG, __name__, "Colour", "x", "__call__"),
        _ext(EXT_CONSTRUCTOR_SINGLE_ARG, "builtins", "exec", "raise SystemExit"),
        _ext(EXT_CONSTRUCTOR_SINGLE_ARG, "builtins", "eval", "1 + 1"),
        _ext(EXT_CONSTRUCTOR_POS_ARGS, "os", "system", ["true"]),
        _ext(EXT_METHOD_SINGLE_ARG, "os", "path", "x", "exists"),
        _ext(EXT_PYDANTIC_V2, "subprocess", "Popen", {"args": "true"}, "x"),
    ],
)
def test_checkpoint_values_keep_to_value_classes(payload):
    value = CheckpointSerializer().loads_typed(("msgpack", payload))

    assert value in (None, {"value": "kw"}, {"args": "true"})


def test_checkpoint_values_keep_unimported_modules_unimported():
    import sys

    name = "naas_abi_sdk.never_imported_by_a_checkpoint"
    payload = _ext(EXT_CONSTRUCTOR_SINGLE_ARG, name, "Anything", "x")

    assert CheckpointSerializer().loads_typed(("msgpack", payload)) is None
    assert name not in sys.modules


def test_checkpoint_values_keep_nested_values_as_data():
    inner = ormsgpack.Ext(
        EXT_CONSTRUCTOR_SINGLE_ARG, ormsgpack.packb([__name__, "record", "nested"])
    )
    payload = ormsgpack.packb(
        ormsgpack.Ext(
            EXT_CONSTRUCTOR_POS_ARGS,
            ormsgpack.packb(["builtins", "set", [[1, inner]]]),
        )
    )

    assert CheckpointSerializer().loads_typed(("msgpack", payload)) == {1, None}


def test_checkpoint_serializer_keeps_messages_and_values_round_tripping():
    # This module's value classes are rebuilt only once its package is named.
    serde = CheckpointSerializer(packages=(__name__,))
    state = {
        "messages": [
            HumanMessage(content="hi", id="h1"),
            AIMessage(
                content="",
                id="a1",
                tool_calls=[{"name": "t", "args": {"x": 1}, "id": "c1"}],
            ),
            ToolMessage(content="ok", tool_call_id="c1", id="t1"),
        ],
        "at": datetime.datetime(2026, 1, 2, 3, 4, 5, tzinfo=datetime.timezone.utc),
        "day": datetime.date(2026, 1, 2),
        "id": uuid.UUID(int=7),
        "tags": {"a", "b"},
        "amount": decimal.Decimal("1.50"),
        "colour": Colour.RED,
        "secret": SecretStr("redacted"),
    }

    decoded = serde.loads_typed(serde.dumps_typed(state))

    assert decoded == state


def test_checkpoint_values_keep_classes_of_unnamed_packages_as_data():
    stored = CheckpointSerializer(packages=(__name__,)).dumps_typed(Colour.RED)

    assert CheckpointSerializer().loads_typed(stored) is None
    assert CheckpointSerializer(packages=(__name__,)).loads_typed(stored) is Colour.RED


def test_checkpoint_json_values_keep_to_plain_json():
    stored = {"lc": 2, "type": "constructor", "id": [__name__, "record"], "args": [1]}

    decoded = CheckpointSerializer().loads_typed(("json", json.dumps(stored).encode()))

    assert decoded == stored


def test_checkpoint_serializer_keeps_pickles_out():
    with pytest.raises(NotImplementedError):
        CheckpointSerializer().loads_typed(("pickle", b"\x80\x04N."))


def test_checkpoint_documents_keep_the_data_decoder_by_default():
    from naas_abi_sdk.langgraph import DocumentCheckpointSaver

    saver = DocumentCheckpointSaver(object(), agent_id="agent-a")  # type: ignore[arg-type]

    assert isinstance(checkpoint_serde(), CheckpointSerializer)
    assert isinstance(saver.schema.serde.serde, CheckpointSerializer)
    planted = _ext(EXT_CONSTRUCTOR_SINGLE_ARG, __name__, "record", "loaded")
    schema = CheckpointDocuments("agent-a", checkpoint_serde())
    assert schema.load({"kind": "msgpack", "payload": planted}) is None


def _module_with_model(monkeypatch, module_name: str):
    """A value class defined in an imported module named ``module_name``."""
    import sys
    import types

    from pydantic import BaseModel

    module = types.ModuleType(module_name)

    class Report(BaseModel):
        title: str
        score: float

    Report.__module__ = module_name
    module.Report = Report  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, module_name, module)
    return Report


def test_checkpoint_values_keep_langgraph_sends(monkeypatch):
    pytest.importorskip("langgraph.types")  # the agent extra
    from langgraph.types import Command, Interrupt, Send

    Report = _module_with_model(monkeypatch, "naas_abi_marketplace.checkpoint_state")
    report = Report(title="t", score=0.5)
    state = {
        "sends": [
            Send("tools", {"tool_call": {"name": "t", "args": {}}}),
            Send("n", 1),
        ],
        "interrupts": [Interrupt(value={"ask": "ok?"}, id="i-1")],
        "command": Command(goto="n", update={"a": 1}, resume="yes"),
        "messages": [HumanMessage(content="hi", id="h1")],
        "report": report,
    }
    serde = CheckpointSerializer()

    decoded = serde.loads_typed(serde.dumps_typed(state))

    assert decoded["sends"] == state["sends"]
    assert all(isinstance(s, Send) for s in decoded["sends"])
    assert decoded["interrupts"] == state["interrupts"]
    assert decoded["command"] == state["command"]
    assert decoded["messages"] == state["messages"]
    assert decoded["report"] == report and type(decoded["report"]) is Report


def test_checkpoint_values_keep_a_modules_own_classes_when_it_names_its_package(
    monkeypatch,
):
    Report = _module_with_model(monkeypatch, "acme_reports.state")
    stored = CheckpointSerializer().dumps_typed(Report(title="t", score=1.0))

    assert CheckpointSerializer().loads_typed(stored) == {"title": "t", "score": 1.0}
    rebuilt = checkpoint_serde(packages=("acme_reports",)).loads_typed(stored)
    assert type(rebuilt) is Report


def test_document_memory_keeps_the_modules_packages(monkeypatch):
    pytest.importorskip("langgraph.graph")  # the agent extra
    import asyncio

    from naas_abi_sdk.agents import hosting
    from naas_abi_sdk.langgraph import DocumentCheckpointSaver

    async def no_setup(self):
        return None

    monkeypatch.setattr(DocumentCheckpointSaver, "setup", no_setup)
    Report = _module_with_model(monkeypatch, "acme_reports.state")
    stored = CheckpointSerializer().dumps_typed(Report(title="t", score=1.0))

    saver = asyncio.run(
        hosting.document_memory(object(), "acme.agent.v1", packages=("acme_reports",))
    )

    assert type(saver.serde.loads_typed(stored)) is Report
