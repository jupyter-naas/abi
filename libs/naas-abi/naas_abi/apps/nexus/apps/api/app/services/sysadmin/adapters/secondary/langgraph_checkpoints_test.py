import importlib
import json
import pickle
import secrets

import ormsgpack
import pytest
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.langgraph_checkpoints import (
    CHECKPOINT_COLLECTIONS,
    WRITE_COLLECTIONS,
    checkpoint_attributes,
    checkpoint_view,
    decode_typed,
    document_key,
    tail_references,
    write_attributes,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.tests.langgraph_fixtures import (
    written,
    written_v1,
)


@pytest.fixture
def token():
    return secrets.token_hex(8)


@pytest.fixture(params=["v2", "v1"])
def docs(request, token):
    return written(token) if request.param == "v2" else written_v1(token)


@pytest.fixture
def fetched(docs):
    """Schema 2 values by ref, as a reader fetches them (none for schema 1)."""
    return {data["ref"]: data for _, _, data in docs if "ref" in data}


def by_collection(docs, collections):
    return [data for c, _, data in docs if c in collections]


CHECKPOINTS, WRITES = CHECKPOINT_COLLECTIONS, WRITE_COLLECTIONS


def test_decodes_a_conversation_without_importing_anything(docs, fetched, monkeypatch):
    def refuse(name, *args, **kwargs):
        raise AssertionError(f"imported {name}")

    monkeypatch.setattr(importlib, "import_module", refuse)
    latest = by_collection(docs, CHECKPOINTS)[1]

    view = checkpoint_view(latest, [], None, fetched)

    assert [m["role"] for m in view["messages"]] == ["system", "human", "ai", "tool", "ai"]
    call = view["messages"][2]
    assert call["tool_calls"] == [
        {"id": "call-1", "name": "Researcher", "args": {"prompt": "JetStream"}}
    ]
    assert call["usage"] == {"input_tokens": 120, "output_tokens": 8, "total_tokens": 128}
    assert call["model"] == "gpt-5.5"
    assert (
        view["messages"][3].items()
        >= {
            "role": "tool",
            "tool_call_id": "call-1",
            "name": "Researcher",
            "content": "NATS persistence.",
        }.items()
    )
    assert view["messages"][4]["content"] == "JetStream is \nNATS persistence."
    assert view["step"] == 3 and view["source"] == "loop"
    assert view["channels"]["current_active_agent"] == "Researcher"
    assert view["thread_id"] == "t-1" and view["agent_id"] == "agent-a"


def test_secrets_in_state_are_masked(docs, fetched, token):
    latest = by_collection(docs, CHECKPOINTS)[1]

    view = checkpoint_view(latest, [], None, fetched)

    assert token not in json.dumps(view)
    assert view["channels"]["credentials"]["value"] == "••••••"


def test_the_parent_and_pending_writes_are_linked(docs, fetched):
    first, latest = by_collection(docs, CHECKPOINTS)
    writes = by_collection(docs, WRITES)
    parent = document_key("agent-a", "t-1", "", first["checkpoint_id"])

    view = checkpoint_view(latest, writes, f"ns/checkpoints/{parent}", fetched)

    assert latest["parent_id"] == first["checkpoint_id"]
    assert [i for c, i, d in docs if c in CHECKPOINTS][0] == parent
    assert view["parent_entry"] == f"ns/checkpoints/{parent}"
    assert [(w["channel"], w["task_path"]) for w in view["writes"]] == [
        ("messages", "~__pregel_pull, call_model"),
        ("branch:to:tools", "~__pregel_pull, call_model"),
    ]
    assert view["writes"][0]["value"][0]["content"] == "Partial answer"
    assert view["writes"][1]["value"] is None


def test_listing_attributes_summarize_a_checkpoint_and_a_write(docs, fetched):
    latest = by_collection(docs, CHECKPOINTS)[1]
    # A listing reads only the conversation's tail, not every message.
    tail = {}
    while wanted := tail_references(latest, tail):
        tail.update((ref, fetched[ref]) for ref, _ in wanted)
    assert len(tail) <= 3

    attributes = checkpoint_attributes(latest, tail)
    write = write_attributes(by_collection(docs, WRITES)[0])

    assert (
        attributes.items()
        >= {
            "thread": "t-1",
            "agent": "agent-a",
            "step": "3",
            "source": "loop",
            "messages": "5",
        }.items()
    )
    assert attributes["last"] == "ai: JetStream is NATS persistence."
    assert (
        attributes["summary"] == "step 3 · loop · 5 messages · ai: JetStream is NATS persistence."
    )
    assert (
        write.items()
        >= {
            "thread": "t-1",
            "channel": "messages",
            "task": "~__pregel_pull, call_model",
            "index": "0",
        }.items()
    )
    assert write["summary"].startswith("messages ← ")


def test_unknown_types_stay_descriptions():
    inner = ormsgpack.packb(("no_such_module.deep", "Thing", {"a": 1}))
    payload = ormsgpack.packb({"x": ormsgpack.Ext(2, inner)})

    assert decode_typed({"kind": "msgpack", "payload": payload}) == {
        "x": {"$type": "no_such_module.deep.Thing", "a": 1}
    }


class _Tripwire:
    loaded = False

    def __reduce__(self):
        return (_Tripwire._trip, ())

    @staticmethod
    def _trip():
        _Tripwire.loaded = True


def test_pickle_is_never_loaded():
    payload = pickle.dumps(_Tripwire())

    shown = decode_typed({"kind": "pickle", "payload": payload})

    assert not _Tripwire.loaded
    assert shown == {"$type": "<pickle>", "size": len(payload), "note": "not decoded"}


def test_bad_payloads_do_not_raise():
    assert decode_typed({"kind": "msgpack", "payload": b"\xc1\xc1"}) == {
        "$type": "<undecodable msgpack>",
        "size": 2,
    }
    assert decode_typed({"kind": "null", "payload": b""}) is None
    assert decode_typed({"kind": "bytes", "payload": b"abc"}) == "<3 bytes>"
