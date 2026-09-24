"""Unit tests for VectorStorePrimaryAdapterNATS's auth/dispatch/error-mapping.

None of these need a real NATS server: each handler is invoked directly
against a minimal fake ``Request`` that records whatever gets passed to
``respond``, matching the "test the handler logic directly" option called
out for this adapter (see the object_storage sibling test's docstring).

The stub ``IVectorStorePort`` below is plain Python lists/dicts -- no real
vector math -- since the point of these tests is round-tripping data through
the wire encoding faithfully, not exercising similarity search.
"""

import asyncio
from typing import Any

import numpy as np
from naas_abi_core.engine.nats_auth import issue_service_token
from naas_abi_core.proto.vector_store.v1 import vector_store_pb2
from naas_abi_core.services.vector_store.adapters.primary.vector_store__primary_adapter__NATS import (
    AUTH_HEADER,
    VectorStorePrimaryAdapterNATS,
)
from naas_abi_core.services.vector_store.IVectorStorePort import (
    IVectorStorePort,
    SearchResult,
    VectorDocument,
)

SECRET = "test-shared-secret"


class _FakeRequest:
    """Stands in for nats.micro.request.Request: same ``.data``/``.headers``
    surface, and ``respond`` just records the payload instead of publishing
    it anywhere."""

    def __init__(
        self,
        data: bytes,
        headers: dict[str, str] | None = None,
        subject: str = "abi.svc.vector_store.v1.list_collections",
    ) -> None:
        self.data = data
        self.headers = headers
        self.subject = subject
        self.responses: list[bytes] = []

    async def respond(
        self, data: bytes = b"", headers: dict[str, str] | None = None
    ) -> None:
        self.responses.append(data)


class _StubAdapter(IVectorStorePort):
    """Minimal in-memory IVectorStorePort for driving the handlers."""

    def __init__(self) -> None:
        self.initialized = False
        self.closed = False
        self.collections: dict[str, dict[str, Any]] = {}
        self.vectors: dict[str, dict[str, VectorDocument]] = {}

    def initialize(self) -> None:
        self.initialized = True

    def create_collection(
        self,
        collection_name: str,
        dimension: int,
        distance_metric: str = "cosine",
        **kwargs,
    ) -> None:
        self.collections[collection_name] = {
            "dimension": dimension,
            "distance_metric": distance_metric,
        }
        self.vectors.setdefault(collection_name, {})

    def delete_collection(self, collection_name: str) -> None:
        self.collections.pop(collection_name, None)
        self.vectors.pop(collection_name, None)

    def list_collections(self) -> list[str]:
        return list(self.collections.keys())

    def store_vectors(
        self, collection_name: str, documents: list[VectorDocument]
    ) -> None:
        coll = self.vectors.setdefault(collection_name, {})
        for doc in documents:
            coll[doc.id] = doc

    def search(
        self,
        collection_name: str,
        query_vector: np.ndarray,
        k: int = 10,
        filter: dict[str, Any] | None = None,
        include_vectors: bool = False,
        include_metadata: bool = True,
    ) -> list[SearchResult]:
        results = []
        for doc in self.vectors.get(collection_name, {}).values():
            if filter and any(
                doc.metadata.get(key) != value for key, value in filter.items()
            ):
                continue
            results.append(
                SearchResult(
                    id=doc.id,
                    score=1.0,
                    vector=doc.vector if include_vectors else None,
                    metadata=doc.metadata if include_metadata else None,
                    payload=doc.payload,
                )
            )
            if len(results) >= k:
                break
        return results

    def get_vector(
        self, collection_name: str, vector_id: str, include_vector: bool = True
    ) -> VectorDocument | None:
        doc = self.vectors.get(collection_name, {}).get(vector_id)
        if doc is None:
            return None
        if include_vector:
            return doc
        return VectorDocument(
            id=doc.id, vector=np.array([]), metadata=doc.metadata, payload=doc.payload
        )

    def update_vector(
        self,
        collection_name: str,
        vector_id: str,
        vector: np.ndarray | None = None,
        metadata: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        existing = self.vectors[collection_name][vector_id]
        self.vectors[collection_name][vector_id] = VectorDocument(
            id=vector_id,
            vector=vector if vector is not None else existing.vector,
            metadata=metadata if metadata is not None else existing.metadata,
            payload=payload if payload is not None else existing.payload,
        )

    def delete_vectors(self, collection_name: str, vector_ids: list[str]) -> None:
        coll = self.vectors.get(collection_name, {})
        for vector_id in vector_ids:
            coll.pop(vector_id, None)

    def count_vectors(self, collection_name: str) -> int:
        return len(self.vectors.get(collection_name, {}))

    def close(self) -> None:
        self.closed = True


def _valid_token() -> str:
    return issue_service_token("api", SECRET)


def _list_collections_request() -> bytes:
    return vector_store_pb2.ListCollectionsRequest().SerializeToString()


# ---------------------------------------------------------------------------
# Auth.
# ---------------------------------------------------------------------------


def test_missing_token_returns_unauthenticated():
    adapter = VectorStorePrimaryAdapterNATS(_StubAdapter(), SECRET)
    request = _FakeRequest(data=_list_collections_request(), headers=None)

    asyncio.run(adapter._handle_list_collections(request))

    response = vector_store_pb2.ListCollectionsResponse()
    response.ParseFromString(request.responses[0])
    assert response.HasField("error")
    assert response.error.code == "UNAUTHENTICATED"
    assert response.error.retryable is False


def test_empty_token_header_returns_unauthenticated():
    adapter = VectorStorePrimaryAdapterNATS(_StubAdapter(), SECRET)
    request = _FakeRequest(data=_list_collections_request(), headers={AUTH_HEADER: ""})

    asyncio.run(adapter._handle_list_collections(request))

    response = vector_store_pb2.ListCollectionsResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.code == "UNAUTHENTICATED"


def test_malformed_token_returns_unauthenticated():
    adapter = VectorStorePrimaryAdapterNATS(_StubAdapter(), SECRET)
    request = _FakeRequest(
        data=_list_collections_request(), headers={AUTH_HEADER: "not-a-jwt"}
    )

    asyncio.run(adapter._handle_list_collections(request))

    response = vector_store_pb2.ListCollectionsResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.code == "UNAUTHENTICATED"


def test_token_signed_with_wrong_secret_returns_unauthenticated():
    adapter = VectorStorePrimaryAdapterNATS(_StubAdapter(), SECRET)
    wrong_secret_token = issue_service_token("api", "a-different-secret")
    request = _FakeRequest(
        data=_list_collections_request(), headers={AUTH_HEADER: wrong_secret_token}
    )

    asyncio.run(adapter._handle_list_collections(request))

    response = vector_store_pb2.ListCollectionsResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.code == "UNAUTHENTICATED"


# ---------------------------------------------------------------------------
# Happy path -- one per IVectorStorePort method.
# ---------------------------------------------------------------------------


def test_successful_initialize_returns_no_error():
    stub = _StubAdapter()
    adapter = VectorStorePrimaryAdapterNATS(stub, SECRET)
    request = _FakeRequest(
        data=vector_store_pb2.InitializeRequest().SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.vector_store.v1.initialize",
    )

    asyncio.run(adapter._handle_initialize(request))

    response = vector_store_pb2.InitializeResponse()
    response.ParseFromString(request.responses[0])
    assert not response.HasField("error")
    assert stub.initialized is True


def test_successful_create_collection_returns_no_error():
    stub = _StubAdapter()
    adapter = VectorStorePrimaryAdapterNATS(stub, SECRET)
    request = _FakeRequest(
        data=vector_store_pb2.CreateCollectionRequest(
            collection_name="docs", dimension=4, distance_metric="cosine"
        ).SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.vector_store.v1.create_collection",
    )

    asyncio.run(adapter._handle_create_collection(request))

    response = vector_store_pb2.CreateCollectionResponse()
    response.ParseFromString(request.responses[0])
    assert not response.HasField("error")
    assert stub.collections["docs"] == {"dimension": 4, "distance_metric": "cosine"}


def test_successful_delete_collection_returns_no_error():
    stub = _StubAdapter()
    stub.create_collection("docs", 4)
    adapter = VectorStorePrimaryAdapterNATS(stub, SECRET)
    request = _FakeRequest(
        data=vector_store_pb2.DeleteCollectionRequest(
            collection_name="docs"
        ).SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.vector_store.v1.delete_collection",
    )

    asyncio.run(adapter._handle_delete_collection(request))

    response = vector_store_pb2.DeleteCollectionResponse()
    response.ParseFromString(request.responses[0])
    assert not response.HasField("error")
    assert "docs" not in stub.collections


def test_list_collections_round_trips_names():
    stub = _StubAdapter()
    stub.create_collection("docs", 4)
    stub.create_collection("images", 8)
    adapter = VectorStorePrimaryAdapterNATS(stub, SECRET)
    request = _FakeRequest(
        data=_list_collections_request(),
        headers={AUTH_HEADER: _valid_token()},
    )

    asyncio.run(adapter._handle_list_collections(request))

    response = vector_store_pb2.ListCollectionsResponse()
    response.ParseFromString(request.responses[0])
    assert not response.HasField("error")
    assert sorted(response.collections.names) == ["docs", "images"]


def test_store_vectors_round_trips_documents():
    stub = _StubAdapter()
    stub.create_collection("docs", 3)
    adapter = VectorStorePrimaryAdapterNATS(stub, SECRET)
    document = vector_store_pb2.VectorDocument(
        id="doc-1",
        vector=vector_store_pb2.VectorData(values=[0.1, 0.2, 0.3]),
        metadata={"category": "a"},
        payload={"raw": "x"},
    )
    request = _FakeRequest(
        data=vector_store_pb2.StoreVectorsRequest(
            collection_name="docs", documents=[document]
        ).SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.vector_store.v1.store_vectors",
    )

    asyncio.run(adapter._handle_store_vectors(request))

    response = vector_store_pb2.StoreVectorsResponse()
    response.ParseFromString(request.responses[0])
    assert not response.HasField("error")
    stored = stub.vectors["docs"]["doc-1"]
    assert stored.id == "doc-1"
    np.testing.assert_array_almost_equal(stored.vector, [0.1, 0.2, 0.3], decimal=5)
    assert stored.metadata == {"category": "a"}
    assert stored.payload == {"raw": "x"}


def test_search_round_trips_results():
    stub = _StubAdapter()
    stub.create_collection("docs", 2)
    stub.store_vectors(
        "docs",
        [
            VectorDocument(
                id="doc-1",
                vector=np.array([1.0, 0.0], dtype=np.float32),
                metadata={"category": "a"},
                payload={"raw": "x"},
            )
        ],
    )
    adapter = VectorStorePrimaryAdapterNATS(stub, SECRET)
    request = _FakeRequest(
        data=vector_store_pb2.SearchRequest(
            collection_name="docs",
            query_vector=[1.0, 0.0],
            k=5,
            include_vectors=True,
            include_metadata=True,
        ).SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.vector_store.v1.search",
    )

    asyncio.run(adapter._handle_search(request))

    response = vector_store_pb2.SearchResponse()
    response.ParseFromString(request.responses[0])
    assert not response.HasField("error")
    assert len(response.results.results) == 1
    result = response.results.results[0]
    assert result.id == "doc-1"
    assert result.HasField("vector")
    np.testing.assert_array_almost_equal(result.vector.values, [1.0, 0.0], decimal=5)
    assert dict(result.metadata) == {"category": "a"}


def test_search_with_filter_is_forwarded_to_adapter():
    stub = _StubAdapter()
    stub.create_collection("docs", 2)
    stub.store_vectors(
        "docs",
        [
            VectorDocument(
                id="doc-1",
                vector=np.array([1.0, 0.0], dtype=np.float32),
                metadata={"category": "a"},
            ),
            VectorDocument(
                id="doc-2",
                vector=np.array([0.0, 1.0], dtype=np.float32),
                metadata={"category": "b"},
            ),
        ],
    )
    adapter = VectorStorePrimaryAdapterNATS(stub, SECRET)
    request = _FakeRequest(
        data=vector_store_pb2.SearchRequest(
            collection_name="docs",
            query_vector=[1.0, 0.0],
            k=5,
            filter={"category": "b"},
        ).SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.vector_store.v1.search",
    )

    asyncio.run(adapter._handle_search(request))

    response = vector_store_pb2.SearchResponse()
    response.ParseFromString(request.responses[0])
    assert [r.id for r in response.results.results] == ["doc-2"]


def test_get_vector_found_round_trips_document():
    stub = _StubAdapter()
    stub.create_collection("docs", 2)
    stub.store_vectors(
        "docs",
        [
            VectorDocument(
                id="doc-1",
                vector=np.array([1.0, 2.0], dtype=np.float32),
                metadata={"category": "a"},
                payload={"raw": "x"},
            )
        ],
    )
    adapter = VectorStorePrimaryAdapterNATS(stub, SECRET)
    request = _FakeRequest(
        data=vector_store_pb2.GetVectorRequest(
            collection_name="docs", vector_id="doc-1", include_vector=True
        ).SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.vector_store.v1.get_vector",
    )

    asyncio.run(adapter._handle_get_vector(request))

    response = vector_store_pb2.GetVectorResponse()
    response.ParseFromString(request.responses[0])
    assert not response.HasField("error")
    assert response.found.HasField("document")
    document = response.found.document
    assert document.id == "doc-1"
    np.testing.assert_array_almost_equal(document.vector.values, [1.0, 2.0], decimal=5)
    assert dict(document.payload) == {"raw": "x"}


def test_get_vector_missing_returns_found_with_no_document():
    stub = _StubAdapter()
    stub.create_collection("docs", 2)
    adapter = VectorStorePrimaryAdapterNATS(stub, SECRET)
    request = _FakeRequest(
        data=vector_store_pb2.GetVectorRequest(
            collection_name="docs", vector_id="missing"
        ).SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.vector_store.v1.get_vector",
    )

    asyncio.run(adapter._handle_get_vector(request))

    response = vector_store_pb2.GetVectorResponse()
    response.ParseFromString(request.responses[0])
    assert not response.HasField("error")
    assert response.HasField("found")
    assert not response.found.HasField("document")


def test_successful_update_vector_returns_no_error():
    stub = _StubAdapter()
    stub.create_collection("docs", 2)
    stub.store_vectors(
        "docs",
        [
            VectorDocument(
                id="doc-1",
                vector=np.array([1.0, 2.0], dtype=np.float32),
                metadata={"category": "a"},
            )
        ],
    )
    adapter = VectorStorePrimaryAdapterNATS(stub, SECRET)
    request = _FakeRequest(
        data=vector_store_pb2.UpdateVectorRequest(
            collection_name="docs",
            vector_id="doc-1",
            metadata={"category": "updated"},
        ).SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.vector_store.v1.update_vector",
    )

    asyncio.run(adapter._handle_update_vector(request))

    response = vector_store_pb2.UpdateVectorResponse()
    response.ParseFromString(request.responses[0])
    assert not response.HasField("error")
    updated = stub.vectors["docs"]["doc-1"]
    assert updated.metadata == {"category": "updated"}
    np.testing.assert_array_almost_equal(updated.vector, [1.0, 2.0], decimal=5)


def test_successful_delete_vectors_returns_no_error():
    stub = _StubAdapter()
    stub.create_collection("docs", 2)
    stub.store_vectors(
        "docs",
        [
            VectorDocument(
                id="doc-1", vector=np.array([1.0, 2.0], dtype=np.float32), metadata={}
            ),
            VectorDocument(
                id="doc-2", vector=np.array([3.0, 4.0], dtype=np.float32), metadata={}
            ),
        ],
    )
    adapter = VectorStorePrimaryAdapterNATS(stub, SECRET)
    request = _FakeRequest(
        data=vector_store_pb2.DeleteVectorsRequest(
            collection_name="docs", vector_ids=["doc-1"]
        ).SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.vector_store.v1.delete_vectors",
    )

    asyncio.run(adapter._handle_delete_vectors(request))

    response = vector_store_pb2.DeleteVectorsResponse()
    response.ParseFromString(request.responses[0])
    assert not response.HasField("error")
    assert list(stub.vectors["docs"].keys()) == ["doc-2"]


def test_count_vectors_round_trips_count():
    stub = _StubAdapter()
    stub.create_collection("docs", 2)
    stub.store_vectors(
        "docs",
        [
            VectorDocument(
                id="doc-1", vector=np.array([1.0, 2.0], dtype=np.float32), metadata={}
            ),
            VectorDocument(
                id="doc-2", vector=np.array([3.0, 4.0], dtype=np.float32), metadata={}
            ),
        ],
    )
    adapter = VectorStorePrimaryAdapterNATS(stub, SECRET)
    request = _FakeRequest(
        data=vector_store_pb2.CountVectorsRequest(
            collection_name="docs"
        ).SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.vector_store.v1.count_vectors",
    )

    asyncio.run(adapter._handle_count_vectors(request))

    response = vector_store_pb2.CountVectorsResponse()
    response.ParseFromString(request.responses[0])
    assert not response.HasField("error")
    assert response.count == 2


def test_successful_close_returns_no_error():
    stub = _StubAdapter()
    adapter = VectorStorePrimaryAdapterNATS(stub, SECRET)
    request = _FakeRequest(
        data=vector_store_pb2.CloseRequest().SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
        subject="abi.svc.vector_store.v1.close",
    )

    asyncio.run(adapter._handle_close(request))

    response = vector_store_pb2.CloseResponse()
    response.ParseFromString(request.responses[0])
    assert not response.HasField("error")
    assert stub.closed is True


# ---------------------------------------------------------------------------
# Generic exception mapping -- IVectorStorePort declares no typed exceptions,
# so every adapter failure maps to INTERNAL (see the module docstring).
# ---------------------------------------------------------------------------


def test_unexpected_exception_maps_to_internal_and_does_not_leak_message():
    class _BoomAdapter(_StubAdapter):
        def list_collections(self) -> list[str]:
            raise RuntimeError("some sensitive internal detail")

    adapter = VectorStorePrimaryAdapterNATS(_BoomAdapter(), SECRET)
    request = _FakeRequest(
        data=_list_collections_request(), headers={AUTH_HEADER: _valid_token()}
    )

    asyncio.run(adapter._handle_list_collections(request))

    response = vector_store_pb2.ListCollectionsResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.code == "INTERNAL"
    assert response.error.retryable is True
    assert "sensitive internal detail" not in response.error.message


# ---------------------------------------------------------------------------
# Lifecycle no-ops.
# ---------------------------------------------------------------------------


def test_stop_without_start_is_a_noop():
    adapter = VectorStorePrimaryAdapterNATS(_StubAdapter(), SECRET)
    asyncio.run(adapter.stop())  # must not raise


def test_owner_emits_audit_for_remote_vector_mutations():
    from unittest.mock import Mock

    from naas_abi_core.services.vector_store.ontologies.modules.VectorStoreEventOntology import (
        CollectionDeleted,
        CollectionEnsured,
        DocumentsDeleted,
    )

    events = []
    primary = VectorStorePrimaryAdapterNATS(
        Mock(), SECRET, event_publisher=events.append
    )
    primary._call_create_collection(
        vector_store_pb2.CreateCollectionRequest(collection_name="test", dimension=3)
    )
    primary._call_delete_vectors(
        vector_store_pb2.DeleteVectorsRequest(
            collection_name="test", vector_ids=["one"]
        )
    )
    primary._call_delete_collection(
        vector_store_pb2.DeleteCollectionRequest(collection_name="test")
    )
    assert [type(e) for e in events] == [
        CollectionEnsured,
        DocumentsDeleted,
        CollectionDeleted,
    ]
    assert events[1].document_count == 1
