import asyncio
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from naas_abi_proto.dataset.v1 import dataset_pb2 as dataset
from naas_abi_proto.document.v1 import document_pb2 as documents
from naas_abi_proto.document.values import encode_data
from naas_abi_proto.object_storage.v1 import object_storage_pb2 as objects
from naas_abi_proto.source_control.v1 import source_control_pb2 as source

from naas_abi_sdk.services import (
    DatasetService,
    DocumentService,
    ObjectStorageService,
    SourceControlService,
)
from naas_abi_sdk.services.errors import ObjectNotFound, VersionConflict
from naas_abi_sdk.services.models import ColumnSpec, DatasetInfo, DatasetSpec, FileWrite
from naas_abi_sdk.transport import RPCError


def test_object_methods_hide_requests_and_responses_and_preserve_domain_error():
    client = AsyncMock()
    client.get_object.return_value = objects.GetObjectResponse(content=b"hello")
    client.put_object.return_value = objects.PutObjectResponse()
    client.list_objects.return_value = objects.ListObjectsResponse(
        keys=objects.Keys(keys=["a", "b"])
    )
    service = ObjectStorageService(client)
    assert asyncio.run(service.get_object("prefix", "key")) == b"hello"
    assert client.get_object.call_args.args[0].key == "key"
    assert asyncio.run(service.put_object("prefix", "key", b"hello")) is None
    assert asyncio.run(service.list_objects()) == ["a", "b"]
    client.get_object.side_effect = RPCError("OBJECT_NOT_FOUND", "missing")
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
