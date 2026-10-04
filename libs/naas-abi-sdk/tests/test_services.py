import asyncio
import json
from datetime import date, datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from naas_abi_proto.dataset.v1 import dataset_pb2 as dataset
from naas_abi_proto.document.v1 import document_pb2 as documents
from naas_abi_proto.document.values import encode_data
from naas_abi_proto.object_storage.v1 import object_storage_pb2 as objects
from naas_abi_proto.source_control.v1 import source_control_pb2 as source
from naas_abi_proto.transfer.v1 import transfer_pb2 as transfer

from naas_abi_sdk.services import (
    DatasetService,
    DocumentService,
    ObjectStorageService,
    SourceControlService,
)
from naas_abi_sdk.services.errors import ObjectNotFound, VersionConflict
from naas_abi_sdk.services.models import ColumnSpec, DatasetInfo, DatasetSpec, FileWrite
from naas_abi_sdk.transport import RPCError

BIG = 2**60 + 1


def test_dataset_query_keeps_integers_exact():
    client = AsyncMock()
    client.query.return_value = dataset.QueryResponse(
        query_result=dataset.QueryResult(
            columns=["id", "n"], json_rows=[f'{{"id":{BIG},"n":42}}'.encode()]
        )
    )
    service = DatasetService(client)

    result = asyncio.run(service.query("SELECT 1", namespace="acme"))

    assert result.columns == ["id", "n"]
    assert result.rows == [{"id": BIG, "n": 42}]
    assert type(result.rows[0]["n"]) is int
    request = client.query.call_args.args[0]
    assert request.accept_json_rows and request.namespace == "acme"


def test_dataset_query_still_reads_an_older_engine_struct_rows():
    client = AsyncMock()
    result = dataset.QueryResult(columns=["n"])
    result.rows.add().update({"n": 42})
    client.query.return_value = dataset.QueryResponse(query_result=result)

    assert asyncio.run(DatasetService(client).query("SELECT 1")).rows == [{"n": 42.0}]


def test_dataset_flush_and_compact_ask_for_exact_rows():
    client = AsyncMock()
    answer = dataset.QueryResult(columns=["n"], json_rows=[b'{"n":3}'])
    client.flush.return_value = dataset.FlushResponse(query_result=answer)
    client.compact.return_value = dataset.CompactResponse(query_result=answer)
    service = DatasetService(client)

    assert asyncio.run(service.flush("t")).rows == [{"n": 3}]
    assert asyncio.run(service.compact("t")).rows == [{"n": 3}]
    assert client.flush.call_args.args[0].accept_json_rows
    assert client.compact.call_args.args[0].accept_json_rows


def test_dataset_write_sends_exact_rows_and_struct_rows_for_older_engines():
    client = AsyncMock()
    client.write.return_value = dataset.WriteResponse(
        info=dataset.DatasetInfo(name="t", namespace="default")
    )
    service = DatasetService(client)

    asyncio.run(service.write("t", [{"id": BIG, "when": date(2026, 10, 4)}]))

    request = client.write.call_args.args[0]
    assert [json.loads(row) for row in request.json_rows] == [
        {"id": BIG, "when": "2026-10-04"}
    ]
    assert request.rows[0]["id"] == float(BIG)
    assert request.rows[0]["when"] == "2026-10-04"


def test_object_methods_hide_requests_and_responses_and_preserve_domain_error():
    client = AsyncMock()
    client.list_objects.return_value = objects.ListObjectsResponse(
        keys=objects.Keys(keys=["a", "b"])
    )
    client._transport.connect.return_value = SimpleNamespace(max_payload=8192)
    state = {}

    async def call(subject, request, response_type, **_options):
        if subject.endswith(".open"):
            metadata = objects.GetObjectRequest.FromString(request.metadata)
            if metadata.key == "missing":
                raise RPCError("OBJECT_NOT_FOUND", "missing")
            state.update(operation=request.operation, key=metadata.key)
            return transfer.OpenResponse(id="one", chunk_bytes=4096)
        if subject.endswith(".read"):
            if state["operation"] == "put" or request.sequence:
                return transfer.ReadResponse(done=True, sequence=request.sequence)
            return transfer.ReadResponse(data=b"hello", frame_end=True)
        return response_type()

    client._transport.call.side_effect = call
    service = ObjectStorageService(client)
    assert asyncio.run(service.get_object("prefix", "key")) == b"hello"
    assert state["key"] == "key"
    assert asyncio.run(service.put_object("prefix", "key", b"hello")) is None
    assert asyncio.run(service.list_objects()) == ["a", "b"]
    with pytest.raises(ObjectNotFound):
        asyncio.run(service.get_object("prefix", "missing"))


def test_dataset_enums_structs_and_nested_dtos():
    client = AsyncMock()
    client.create.return_value = dataset.CreateResponse(
        info=dataset.DatasetInfo(
            name="rows",
            namespace="default",
            columns=[dataset.ColumnSpec(name="id", type=dataset.COLUMN_TYPE_STRING)],
        )
    )
    service = DatasetService(client)
    result = asyncio.run(
        service.create(
            DatasetSpec(name="rows", columns=[ColumnSpec(name="id", type="string")])
        )
    )
    assert isinstance(result, DatasetInfo)
    assert result.columns[0].type == "string"
    assert client.create.call_args.args[0].spec.namespace == "default"
    client.write.return_value = client.create.return_value
    asyncio.run(service.write("rows", [{"id": "one"}], mode="replace", snapshot_id=0))
    request = client.write.call_args.args[0]
    assert request.mode == dataset.WRITE_MODE_REPLACE
    assert request.HasField("snapshot_id") and request.snapshot_id == 0
    assert request.rows[0]["id"] == "one"


def test_source_control_selects_text_and_binary_oneof():
    client = AsyncMock()
    client.upsert_files.return_value = source.UpsertFilesResponse(
        commit=source.Commit(sha="abc")
    )
    service = SourceControlService(client)
    result = asyncio.run(
        service.upsert_files(
            repo_id="repo",
            files=[FileWrite("text", "hello"), FileWrite("binary", b"\x00\xff")],
            message="create",
            branch="main",
        )
    )
    assert result.sha == "abc"
    request = client.upsert_files.call_args.args[0]
    assert request.files[0].HasField("text_content")
    assert not request.files[0].HasField("binary_content")
    assert request.files[1].binary_content == b"\x00\xff"


def test_document_paging_materializes_predicates_and_preserves_cas():
    client = AsyncMock()
    now = datetime.now(timezone.utc).isoformat()

    def doc(id):
        return documents.Document(
            id=id,
            data=encode_data({"binary": b"\x00", "large": 2**60}),
            created_at=now,
            updated_at=now,
            version=7,
        )

    client.find.side_effect = [
        documents.FindResponse(items=[doc("a")], cursor="next"),
        documents.FindResponse(items=[doc("b")]),
    ]
    service = DocumentService(client)

    async def scenario():
        return [
            item
            async for item in service.iterate(
                "records",
                where=((k, o, v) for k, o, v in [("kind", "eq", "run")]),
                batch=1,
            )
        ]

    values = asyncio.run(scenario())
    assert [v.id for v in values] == ["a", "b"]
    assert values[0].data == {"binary": b"\x00", "large": 2**60}
    assert all(
        call.args[0].where[0].field == "kind" for call in client.find.call_args_list
    )
    client.put.side_effect = RPCError("VERSION_CONFLICT", "changed")
    with pytest.raises(VersionConflict):
        asyncio.run(service.put("records", "a", {}, if_version=0))
    assert client.put.call_args.args[0].HasField("if_version")
    assert client.put.call_args.args[0].if_version == 0


def test_keyvalue_optional_error_detail_is_not_a_result_field():
    from naas_abi_proto.keyvalue.v1 import keyvalue_pb2 as pb

    from naas_abi_sdk.services.keyvalue import KeyValueService

    client = AsyncMock()
    client.get.return_value = pb.GetResponse(value=b"hello")
    client.set.return_value = pb.SetResponse()
    client.set_if_not_exists.return_value = pb.SetIfNotExistsResponse(ok_value=True)
    service = KeyValueService(client)
    assert asyncio.run(service.get("key")) == b"hello"
    assert asyncio.run(service.set("key", b"value")) is None
    assert asyncio.run(service.set_if_not_exists("key", b"value")) is True


def test_cache_reads_hot_then_cold_writes_cold_and_deletes_all_tiers():
    from unittest.mock import MagicMock

    from naas_abi_proto.cache.v1 import cache_pb2 as pb

    from naas_abi_sdk.services.cache import CacheService

    client = MagicMock()
    client.describe = AsyncMock(return_value=pb.DescribeResponse(tiers=["hot", "cold"]))
    hot, cold = AsyncMock(), AsyncMock()
    client.tier.side_effect = [hot, cold, cold, hot, cold]
    hot.get.side_effect = RPCError("CACHE_NOT_FOUND", "missing")
    cold.get.return_value = pb.GetResponse(
        value=pb.CachedData(data='{"ok": true}', data_type=pb.DATA_TYPE_JSON)
    )
    service = CacheService(client)
    assert asyncio.run(service.get("key")) == {"ok": True}
    asyncio.run(service.set_binary("key", b"hello"))
    assert cold.set.call_args.args[0].value.data == "aGVsbG8="
    hot.set.assert_not_awaited()
    asyncio.run(service.delete("key"))
    hot.delete.assert_awaited_once()
    cold.delete.assert_awaited_once()


def test_rdf_graph_and_query_values():
    rdf = pytest.importorskip("rdflib")
    from naas_abi_proto.triple_store.v1 import triple_store_pb2 as pb

    from naas_abi_sdk.services.triple_store import TripleStoreService

    client = AsyncMock()
    client.get.return_value = pb.GetResponse(triples_nt=b'<urn:s> <urn:p> "hello" .\n')
    service = TripleStoreService(client)
    graph = asyncio.run(service.get())
    assert list(graph.objects()) == [rdf.Literal("hello")]
    asyncio.run(service.insert(graph, rdf.URIRef("urn:graph")))
    request = client.insert.call_args.args[0]
    assert request.graph_name == "urn:graph"
    assert len(rdf.Graph().parse(data=request.triples_nt, format="nt")) == 1


def test_transfer_timeout_never_falls_back_to_unary_write():
    from io import BytesIO

    client = AsyncMock()
    client._transport.connect.return_value = SimpleNamespace(max_payload=65536)
    client._transport.call.side_effect = TimeoutError("uncertain open")
    service = ObjectStorageService(client)
    with pytest.raises(TimeoutError):
        asyncio.run(service.put_object_stream("prefix", "key", BytesIO(b"hello")))
    client.put_object.assert_not_awaited()
    assert client._transport.call.await_count == 1


# --- streamed triple store reads (docs/adr/20261003_nats-streamed-results.md)


class StreamTransport:
    """The owner side of one transfer stream: a list of frames, read in order."""

    def __init__(self, frames, *, no_responders=False):
        self.frames, self.no_responders = list(frames), no_responders
        self.opened, self.closed, self.read = [], [], 0

    async def connect(self):
        return SimpleNamespace(max_payload=1024 * 1024)

    async def call(self, subject, request, response_type, transfer=None):
        operation = subject.rsplit(".", 1)[1]
        if operation == "open":
            if self.no_responders:
                from nats.errors import NoRespondersError

                raise NoRespondersError()
            self.opened.append((request.operation, request.metadata))
            return response_type(id=f"{'a' * 32}:s", chunk_bytes=request.chunk_bytes)
        if operation == "start":
            return response_type()
        if operation == "close":
            self.closed.append(request.id)
            return response_type()
        if self.read >= len(self.frames):
            return response_type(done=True, sequence=request.sequence)
        self.read += 1
        return response_type(
            data=self.frames[self.read - 1], frame_end=True, sequence=request.sequence
        )


def test_query_stream_reads_select_rows_frame_by_frame():
    rdf = pytest.importorskip("rdflib")
    from naas_abi_proto.triple_store.v1 import triple_store_pb2 as pb

    from naas_abi_sdk.services.triple_store import TripleStoreService

    header = pb.QueryResult(result_type="SELECT")
    header.select.vars.extend(["s", "n"])
    batch = lambda *values: pb.SelectResult(
        rows=[pb.Row(bindings={"s": "<urn:s>", "n": str(v)}) for v in values]
    ).SerializeToString()
    transport = StreamTransport([header.SerializeToString(), batch(1, 2), batch(3)])
    service = TripleStoreService(SimpleNamespace(_transport=transport))

    async def scenario():
        async with service.query_stream("SELECT ?s ?n WHERE {}") as result:
            assert (result.result_type, result.vars) == ("SELECT", ["s", "n"])
            first = await anext(result.rows)
            assert transport.read == 2  # the rest is still on the engine
            rest = [row async for row in result.rows]
        return [first, *rest]

    rows = asyncio.run(scenario())
    assert [int(row["n"]) for row in rows] == [1, 2, 3]
    assert rows[0]["s"] == rdf.URIRef("urn:s")
    assert transport.opened == [
        ("query", pb.QueryRequest(query="SELECT ?s ?n WHERE {}").SerializeToString())
    ]
    assert transport.closed == [f"{'a' * 32}:s"]


def test_export_reads_n_triples_frames_with_shared_blank_nodes():
    pytest.importorskip("rdflib")
    from naas_abi_sdk.services.triple_store import TripleStoreService

    transport = StreamTransport(
        [b'_:x <urn:p> "1" .\n', b'_:x <urn:p> "2" .\n<urn:a> <urn:q> _:x .\n']
    )
    service = TripleStoreService(SimpleNamespace(_transport=transport))

    async def scenario():
        async with service.export("urn:graph") as triples:
            return [triple async for triple in triples]

    triples = asyncio.run(scenario())
    assert len(triples) == 3 and triples[0][0] == triples[2][2]
    assert transport.opened == [("export", b"urn:graph")]


def test_query_stream_falls_back_to_query_on_an_engine_without_streams():
    pytest.importorskip("rdflib")
    from naas_abi_proto.triple_store.v1 import triple_store_pb2 as pb

    from naas_abi_sdk.services.triple_store import TripleStoreService

    client = AsyncMock()
    client._transport = StreamTransport([], no_responders=True)
    client.query.return_value = pb.QueryResponse(
        success=pb.QueryResult(result_type="ASK", ask_answer=True)
    )
    service = TripleStoreService(client)

    async def scenario():
        async with service.query_stream("ASK {}") as result:
            return result.ask_answer

    assert asyncio.run(scenario()) is True


@pytest.mark.parametrize("graph_name", ["http://x/a b", "http://x/>", "relative"])
def test_export_fallback_refuses_a_graph_name_that_is_not_an_iri(graph_name):
    from naas_abi_sdk.services.triple_store import _graph_export_query

    with pytest.raises(ValueError):
        _graph_export_query(graph_name)


def test_dataset_query_stream_reads_rows_frame_by_frame():
    from naas_abi_sdk.services import FACTORIES

    header = dataset.QueryResult(columns=["id", "name"]).SerializeToString()
    batch = dataset.QueryResult(
        json_rows=[f'{{"id":{n},"name":"row {n}"}}'.encode() for n in range(3)]
    )
    transport = StreamTransport([header, batch.SerializeToString()])
    service = FACTORIES["dataset"](SimpleNamespace(_transport=transport))

    async def scenario():
        async with service.query_stream(
            "SELECT id, name FROM t", namespace="acme"
        ) as result:
            assert result.columns == ["id", "name"]
            return [row async for row in result.rows]

    rows = asyncio.run(scenario())
    assert rows == [
        {"id": 0, "name": "row 0"},
        {"id": 1, "name": "row 1"},
        {"id": 2, "name": "row 2"},
    ]
    assert type(rows[0]["id"]) is int
    ((operation, metadata),) = transport.opened
    request = dataset.QueryRequest.FromString(metadata)
    assert request.accept_json_rows
    assert (operation, request.sql, request.namespace) == (
        "query",
        "SELECT id, name FROM t",
        "acme",
    )
    assert transport.closed == [f"{'a' * 32}:s"]
