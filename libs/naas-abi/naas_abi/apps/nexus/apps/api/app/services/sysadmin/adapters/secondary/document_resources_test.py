import asyncio
import json
from datetime import UTC, datetime

import pytest
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.document_resources import (
    DocumentResources,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.langgraph_checkpoints import (
    CHECKPOINTS,
    LEGACY_CHECKPOINTS,
    LEGACY_WRITES,
    WRITES,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.contracts import (
    ServiceResourcesContract,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources import (
    InvalidResource,
    ResourceNotFound,
    UnsupportedOperation,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.tests import fixtures
from naas_abi_core.services.document.adapters.secondary.DocumentSecondaryAdapterSQLite import (
    DocumentSecondaryAdapterSQLite,
)
from naas_abi_core.services.document.DocumentPort import CollectionSpec
from naas_abi_core.services.document.DocumentService import DocumentService


def run(coro):
    return asyncio.run(coro)


@pytest.fixture
def root(tmp_path):
    backend = DocumentSecondaryAdapterSQLite(str(tmp_path / "documents.sqlite"))
    yield DocumentService._for_engine(backend)
    backend.close()


def _seed(root: DocumentService) -> DocumentService:
    records = root.for_namespace("acme.module")
    records.ensure_collection(CollectionSpec(name="records"))
    for name, value in fixtures.SEED_ITEMS.items():
        records.put("records", name, {"value": value.decode()})
    other = root.for_namespace("naas_abi")
    other.ensure_collection(CollectionSpec(name="agent_runs"))
    other.ensure_collection(CollectionSpec(name="checkpoints"))
    return root


class TestDocumentResources(ServiceResourcesContract):
    base = "acme.module/records"
    sized = False

    def encode(self, text: str) -> bytes:
        return json.dumps({"value": text}).encode()

    def assert_shown(self, shown, text):
        assert shown is not None and json.loads(shown)["value"] == text

    def assert_downloaded(self, data, text):
        assert json.loads(data)["value"] == text

    @pytest.fixture
    def resources(self, root):
        return DocumentResources(_seed(root))


@pytest.fixture
def documents(root):
    return DocumentResources(_seed(root))


def test_namespaces_then_collections_are_containers(documents):
    namespaces = run(documents.list("")).entries
    collections = run(documents.list("naas_abi")).entries

    assert [(e.id, e.name, e.kind) for e in namespaces] == [
        ("acme.module", "acme.module", "container"),
        ("naas_abi", "naas_abi", "container"),
    ]
    assert [(e.id, e.kind, e.actions) for e in collections] == [
        ("naas_abi/agent_runs", "container", ("delete",)),
        ("naas_abi/checkpoints", "container", ("delete",)),
    ]
    assert run(documents.stat("naas_abi")).kind == "container"
    assert run(documents.stat("naas_abi/checkpoints")).kind == "container"


def test_unknown_namespaces_and_collections_are_not_found(documents):
    for resource_id in ("nope.module", "acme.module/nope"):
        with pytest.raises(ResourceNotFound):
            run(documents.list(resource_id))
        with pytest.raises(ResourceNotFound):
            run(documents.stat(resource_id))


def test_deleting_a_collection_drops_it_but_a_namespace_cannot_be_deleted(documents, root):
    run(documents.delete("naas_abi/checkpoints"))

    assert root.for_namespace("naas_abi").collections() == ["agent_runs"]
    with pytest.raises(UnsupportedOperation):
        run(documents.delete("naas_abi"))
    with pytest.raises(InvalidResource):
        run(documents.delete(""))


def test_documents_show_their_version_and_timestamps(documents):
    entry = run(documents.stat("acme.module/records/alpha"))

    assert entry.attributes["version"] == "1"
    assert entry.modified is not None and entry.modified.endswith("+00:00")
    assert "created_at" in entry.attributes


def test_tagged_values_round_trip_through_read_and_write(documents, root):
    view = root.for_namespace("acme.module")
    view.put(
        "records",
        "typed",
        {
            "at": datetime(2026, 10, 2, 8, 0, tzinfo=UTC),
            "blob": b"\x00\xff",
            "$dollar": "kept",
        },
    )

    shown = run(documents.read("acme.module/records/typed")).content.text
    run(documents.write("acme.module/records/typed", shown.encode()))

    data = view.get("records", "typed").data
    assert data == {
        "at": datetime(2026, 10, 2, 8, 0, tzinfo=UTC),
        "blob": b"\x00\xff",
        "$dollar": "kept",
    }
    assert view.get("records", "typed").version == 2


@pytest.mark.parametrize(
    "body",
    [b"not json", b"[1, 2]", b'"text"', b'{"at": {"$t": "datetime", "$v": "nope"}}'],
)
def test_writes_need_a_valid_json_object(documents, body):
    with pytest.raises(InvalidResource):
        run(documents.write("acme.module/records/bad", body))


@pytest.mark.parametrize("resource_id", ["acme.module", "acme.module/records", ""])
def test_only_documents_can_be_written(documents, resource_id):
    with pytest.raises(InvalidResource):
        run(documents.write(resource_id, b"{}"))


def test_writing_into_a_missing_collection_is_invalid(documents):
    with pytest.raises(InvalidResource, match="collection"):
        run(documents.write("acme.module/missing/doc", b"{}"))


def test_document_ids_may_contain_slashes(documents, root):
    run(documents.write("acme.module/records/a/b/c", b'{"value": "deep"}'))

    assert root.for_namespace("acme.module").get("records", "a/b/c").data == {"value": "deep"}
    assert run(documents.stat("acme.module/records/a/b/c")).name == "a/b/c"
    with pytest.raises(InvalidResource):
        run(documents.list("acme.module/records/a/b/c"))


def test_names_with_slashes_are_quoted_in_ids(root, documents):
    odd = root.for_namespace("odd/name")
    odd.ensure_collection(CollectionSpec(name="a/b"))
    odd.put("a/b", "doc", {"value": "x"})

    (namespace,) = [e for e in run(documents.list("")).entries if e.name == "odd/name"]
    (collection,) = run(documents.list(namespace.id)).entries
    (document,) = run(documents.list(collection.id)).entries

    assert namespace.id == "odd%2Fname"
    assert (collection.id, collection.name) == ("odd%2Fname/a%2Fb", "a/b")
    assert document.id == "odd%2Fname/a%2Fb/doc"
    assert json.loads(run(documents.read(document.id)).content.text) == {"value": "x"}


def test_a_bad_cursor_is_invalid(documents):
    with pytest.raises(InvalidResource):
        run(documents.list("acme.module/records", cursor="not-a-cursor"))
    with pytest.raises(InvalidResource):
        run(documents.list("", cursor="x"))


def test_listings_carry_counts_and_one_line_summaries(documents, root):
    namespaces = {e.name: e for e in run(documents.list("")).entries}
    collections = {e.name: e for e in run(documents.list("acme.module")).entries}
    (alpha, *_) = run(documents.list("acme.module/records")).entries

    assert namespaces["naas_abi"].attributes["collections"] == "2"
    assert namespaces["naas_abi"].attributes["summary"] == "2 collections"
    assert collections["records"].attributes["documents"] == "3"
    assert collections["records"].attributes["summary"] == "3 documents"
    assert alpha.attributes["summary"] == "value: first value"
    assert alpha.attributes["keys"] == "1"


def test_document_fields_describe_top_level_values_for_columns(documents, root):
    records = root.for_namespace("acme.module")
    records.put(
        "records",
        "rich",
        {
            "title": "  A   long\ntitle  ",
            "count": 3,
            "ok": True,
            "missing": None,
            "when": datetime(2026, 10, 2, 8, tzinfo=UTC),
            "blob": b"\x00\x01",
            "tags": ["a", "b"],
            "nested": {"x": 1},
        },
    )

    entry = run(documents.stat("acme.module/records/rich"))
    fields = json.loads(entry.attributes["fields"])

    assert fields == {
        "title": "A long title",
        "count": 3,
        "ok": True,
        "missing": None,
        "when": "2026-10-02T08:00:00+00:00",
        "blob": "<2 bytes>",
        "tags": "[2 items]",
        "nested": "{1 keys}",
    }
    # Names and titles first, then other scalars; nulls, bytes and nested values skipped.
    assert entry.attributes["summary"] == "title: A long title · count: 3 · ok: True"


def test_reading_a_document_carries_its_whole_value_as_a_json_view(documents):
    detail = run(documents.read("acme.module/records/alpha"))

    assert detail.view == {"type": "json", "value": {"value": "first value"}}


def test_namespace_pages_only_count_the_page(root, monkeypatch):
    documents = DocumentResources(_seed(root))
    looked = []
    original = root.for_namespace

    def spy(namespace):
        looked.append(namespace)
        return original(namespace)

    monkeypatch.setattr(root, "for_namespace", spy)

    page = run(documents.list("", limit=1))

    assert [e.name for e in page.entries] == ["acme.module"]
    assert looked == ["acme.module"]


# --- LangGraph checkpoints -------------------------------------------------------------


def _seed_checkpoints(root: DocumentService, token: str, schema: str = "v2") -> DocumentService:
    from naas_abi.apps.nexus.apps.api.app.services.sysadmin.tests.langgraph_fixtures import (
        written,
        written_v1,
    )
    from naas_abi_core.services.document.DocumentPort import FieldSpec
    from naas_abi_sdk.langgraph_documents import COLLECTIONS, SCOPE_FIELDS

    agents = root.for_namespace("acme.agents")
    collections = dict(COLLECTIONS) | {
        LEGACY_CHECKPOINTS: SCOPE_FIELDS,
        LEGACY_WRITES: SCOPE_FIELDS,
    }
    for collection, fields in collections.items():
        indexed = tuple(FieldSpec(name=f, type="string", indexed=True) for f in fields)
        agents.ensure_collection(CollectionSpec(name=collection, fields=indexed))
    documents = written(token) if schema == "v2" else written_v1(token)
    for collection, key, data in documents:
        agents.put(collection, key, data)
    # A second, older thread of another agent (its own values, as savers scope them).
    for collection, key, data in documents:
        if collection in (CHECKPOINTS, LEGACY_CHECKPOINTS):
            data = data | {"checkpoint_id": "0" + data["checkpoint_id"][1:]}
        elif "ref" not in data:
            continue
        agents.put(collection, "b-" + key, data | {"thread_id": "t-0", "agent_id": "agent-b"})
    return root


@pytest.fixture(params=["v2", "v1"])
def schema(request):
    """(schema, its checkpoints collection, its writes collection)"""
    if request.param == "v2":
        return "v2", CHECKPOINTS, WRITES
    return "v1", LEGACY_CHECKPOINTS, LEGACY_WRITES


def test_checkpoints_list_newest_first_by_thread_with_readable_summaries(root, schema):
    import secrets

    version, checkpoints, _ = schema
    documents = DocumentResources(_seed_checkpoints(root, secrets.token_hex(8), version))

    entries = run(documents.list(f"acme.agents/{checkpoints}")).entries

    assert [(e.attributes["thread"], e.attributes.get("step")) for e in entries] == [
        ("t-1", "3"),
        ("t-1", "-1"),
        ("t-0", "3"),
        ("t-0", "-1"),
    ]
    assert (
        entries[0].attributes["summary"]
        == "step 3 · loop · 5 messages · ai: JetStream is NATS persistence."
    )
    assert entries[0].attributes["agent"] == "agent-a"


def test_reading_a_checkpoint_shows_the_conversation_its_writes_and_parent(root, schema):
    import secrets

    version, checkpoints, _ = schema
    token = secrets.token_hex(8)
    documents = DocumentResources(_seed_checkpoints(root, token, version))
    latest = run(documents.list(f"acme.agents/{checkpoints}")).entries[0]

    detail = run(documents.read(latest.id))

    view = detail.view
    assert view is not None and view["type"] == "checkpoint"
    assert [m["role"] for m in view["messages"]] == ["system", "human", "ai", "tool", "ai"]
    assert [w["channel"] for w in view["writes"]] == ["messages", "branch:to:tools"]
    parent = run(documents.read(view["parent_entry"]))
    assert parent.view is not None and parent.view["step"] == -1
    # The decoded view masks secrets; the raw document keeps the stored bytes.
    assert token not in json.dumps(view)


def test_writes_list_with_their_channel_and_value(root, schema):
    import secrets

    version, _, writes = schema
    documents = DocumentResources(_seed_checkpoints(root, secrets.token_hex(8), version))

    entries = run(documents.list(f"acme.agents/{writes}")).entries
    views = [run(documents.read(e.id)).view for e in entries]

    assert sorted(e.attributes["channel"] for e in entries) == ["branch:to:tools", "messages"]
    values = {
        v["value"]["channel"]: v["value"]["value"] for v in views if v and v["type"] == "json"
    }
    assert values["messages"][0]["content"] == "Partial answer"
    assert values["branch:to:tools"] is None


def test_a_schema_2_view_reads_split_values_and_lists_value_collections_plainly(root):
    import asyncio as aio

    from langchain_core.messages import AIMessage, HumanMessage
    from langgraph.checkpoint.base import empty_checkpoint
    from naas_abi.apps.nexus.apps.api.app.services.sysadmin.tests.langgraph_fixtures import _Capture
    from naas_abi_sdk.langgraph import DocumentCheckpointSaver
    from naas_abi_sdk.langgraph_documents import PART_SIZE, PARTS

    capture = _Capture()
    saver = DocumentCheckpointSaver(capture, agent_id="agent-a")  # type: ignore[arg-type]
    checkpoint = empty_checkpoint()
    huge = "z" * (2 * PART_SIZE)
    checkpoint["channel_values"] = {"messages": [HumanMessage("hi"), AIMessage(huge)]}
    checkpoint["channel_versions"] = {"messages": 1}
    aio.run(
        saver.aput(
            {"configurable": {"thread_id": "t-9", "checkpoint_ns": ""}}, checkpoint, {"step": 0}, {}
        )
    )
    agents = _seed_checkpoints(root, "token").for_namespace("acme.agents")
    for collection, key, data in capture.puts:
        agents.put(collection, key, data)
    documents = DocumentResources(root)

    entries = run(documents.list(f"acme.agents/{CHECKPOINTS}")).entries
    newest = next(e for e in entries if e.attributes["thread"] == "t-9")
    view = run(documents.read(newest.id)).view

    assert newest.attributes["messages"] == "2"
    assert view is not None and view["messages"][1]["content"] == huge[:20_000]
    assert view["messages"][1]["truncated"] == len(huge)
    parts = run(documents.list(f"acme.agents/{PARTS}")).entries
    assert len(parts) == 3 and "summary" in parts[0].attributes


class _OnePerPage:
    """A document view whose pages hold one item, as a tight byte budget cuts them."""

    def __init__(self, view):
        self._view = view

    def __getattr__(self, name):
        return getattr(self._view, name)

    def find(self, collection, **kwargs):
        return self._view.find(collection, **{**kwargs, "max_bytes": 1})

    def iterate(self, collection, **kwargs):
        return self._view.iterate(collection, **{**kwargs, "max_bytes": 1})


def test_value_reads_follow_every_page_when_pages_are_cut(root):
    from naas_abi_sdk.langgraph_documents import BLOBS

    view = root.for_namespace("acme.agents")
    view.ensure_collection(CollectionSpec(name=BLOBS))
    refs = [f"b{n}" for n in range(5)]
    for n, ref in enumerate(refs):
        view.put(BLOBS, f"k{n}", {"agent_id": "a", "thread_id": "t", "ref": ref, "value": n})

    found = DocumentResources(root)._fetch(
        _OnePerPage(view), {"agent_id": "a", "thread_id": "t"}, [(ref, 10) for ref in refs]
    )

    assert sorted(d["value"] for d in found) == list(range(5))
