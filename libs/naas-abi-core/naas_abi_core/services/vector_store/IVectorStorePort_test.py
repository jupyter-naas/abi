from abc import ABC

import numpy as np
import pytest

from .IVectorStorePort import IVectorStorePort, VectorDocument


class GenericVectorStoreAdapterTest(ABC):
    @pytest.fixture
    def adapter(self) -> IVectorStorePort:
        raise NotImplementedError("Subclasses must provide an adapter fixture")

    @pytest.fixture
    def test_collection_name(self) -> str:
        return "test_collection"

    @pytest.fixture
    def test_dimension(self) -> int:
        return 128

    @pytest.fixture
    def sample_vectors(self) -> list[np.ndarray]:
        np.random.seed(42)
        return [
            np.random.randn(128).astype(np.float32) for _ in range(5)
        ]

    @pytest.fixture
    def sample_documents(self, sample_vectors) -> list[VectorDocument]:
        return [
            VectorDocument(
                id=f"doc_{i}",
                vector=vector,
                metadata={"category": f"cat_{i % 2}", "index": i},
                payload={"data": f"payload_{i}"}
            )
            for i, vector in enumerate(sample_vectors)
        ]

    def test_initialize(self, adapter):
        adapter.initialize()
        assert True

    def test_create_and_list_collections(
        self, adapter, test_collection_name, test_dimension
    ):
        adapter.initialize()
        
        adapter.create_collection(
            test_collection_name, test_dimension, distance_metric="cosine"
        )
        
        collections = adapter.list_collections()
        assert test_collection_name in collections

    def test_store_and_retrieve_vectors(
        self, adapter, test_collection_name, test_dimension, sample_documents
    ):
        adapter.initialize()
        
        adapter.create_collection(test_collection_name, test_dimension)
        
        adapter.store_vectors(test_collection_name, sample_documents)
        
        retrieved = adapter.get_vector(
            test_collection_name, "doc_0", include_vector=True
        )
        
        assert retrieved is not None
        assert retrieved.id == "doc_0"
        assert retrieved.metadata["category"] == "cat_0"
        assert retrieved.payload["data"] == "payload_0"
        assert retrieved.vector is not None
        np.testing.assert_array_almost_equal(
            retrieved.vector, sample_documents[0].vector, decimal=5
        )

    def test_search_vectors(
        self, adapter, test_collection_name, test_dimension, sample_documents
    ):
        adapter.initialize()
        
        adapter.create_collection(test_collection_name, test_dimension)
        adapter.store_vectors(test_collection_name, sample_documents)
        
        query_vector = sample_documents[0].vector
        results = adapter.search(
            test_collection_name,
            query_vector,
            k=3,
            include_metadata=True
        )
        
        assert len(results) <= 3
        assert results[0].id == "doc_0"
        assert results[0].score >= 0.99

    def test_search_with_filter(
        self, adapter, test_collection_name, test_dimension, sample_documents
    ):
        adapter.initialize()
        
        adapter.create_collection(test_collection_name, test_dimension)
        adapter.store_vectors(test_collection_name, sample_documents)
        
        query_vector = sample_documents[0].vector
        results = adapter.search(
            test_collection_name,
            query_vector,
            k=10,
            filter={"category": "cat_0"},
            include_metadata=True
        )
        
        for result in results:
            assert result.metadata["category"] == "cat_0"

    def test_update_vector(
        self, adapter, test_collection_name, test_dimension, sample_documents
    ):
        adapter.initialize()
        
        adapter.create_collection(test_collection_name, test_dimension)
        adapter.store_vectors(test_collection_name, [sample_documents[0]])
        
        new_metadata = {"category": "updated", "new_field": "value"}
        adapter.update_vector(
            test_collection_name,
            "doc_0",
            metadata=new_metadata
        )
        
        retrieved = adapter.get_vector(test_collection_name, "doc_0")
        assert retrieved.metadata["category"] == "updated"
        assert retrieved.metadata["new_field"] == "value"

    def test_delete_vectors(
        self, adapter, test_collection_name, test_dimension, sample_documents
    ):
        adapter.initialize()
        
        adapter.create_collection(test_collection_name, test_dimension)
        adapter.store_vectors(test_collection_name, sample_documents)
        
        initial_count = adapter.count_vectors(test_collection_name)
        assert initial_count == len(sample_documents)
        
        adapter.delete_vectors(test_collection_name, ["doc_0", "doc_1"])
        
        final_count = adapter.count_vectors(test_collection_name)
        assert final_count == initial_count - 2
        
        deleted_doc = adapter.get_vector(test_collection_name, "doc_0")
        assert deleted_doc is None

    def test_count_vectors(
        self, adapter, test_collection_name, test_dimension, sample_documents
    ):
        adapter.initialize()
        
        adapter.create_collection(test_collection_name, test_dimension)
        
        count_empty = adapter.count_vectors(test_collection_name)
        assert count_empty == 0
        
        adapter.store_vectors(test_collection_name, sample_documents)
        
        count_filled = adapter.count_vectors(test_collection_name)
        assert count_filled == len(sample_documents)

    def test_delete_collection(
        self, adapter, test_collection_name, test_dimension
    ):
        adapter.initialize()
        
        adapter.create_collection(test_collection_name, test_dimension)
        
        collections_before = adapter.list_collections()
        assert test_collection_name in collections_before
        
        adapter.delete_collection(test_collection_name)
        
        collections_after = adapter.list_collections()
        assert test_collection_name not in collections_after

    def test_close(self, adapter):
        adapter.initialize()
        adapter.close()
        assert True
    # ------------------------------------------------------------------
    # Paging through a collection and describing it (admin browsing).
    # ------------------------------------------------------------------

    def _walk(self, adapter, collection_name, limit, include_vectors=False):
        ids, cursor = [], None
        for _ in range(100):
            page = adapter.list_vectors(
                collection_name,
                limit=limit,
                cursor=cursor,
                include_vectors=include_vectors,
            )
            assert len(page.documents) <= limit
            ids += [document.id for document in page.documents]
            cursor = page.next_cursor
            if cursor is None:
                return ids
        raise AssertionError("list_vectors never ended")

    def test_list_vectors_pages_through_every_document_once(
        self, adapter, test_collection_name, test_dimension, sample_documents
    ):
        adapter.initialize()
        adapter.create_collection(test_collection_name, test_dimension)
        adapter.store_vectors(test_collection_name, sample_documents)

        ids = self._walk(adapter, test_collection_name, limit=2)

        assert sorted(ids) == sorted(d.id for d in sample_documents)
        assert len(ids) == len(set(ids))
        # Stable order: walking again, with another page size, gives the same ids.
        assert self._walk(adapter, test_collection_name, limit=3) == ids
        assert self._walk(adapter, test_collection_name, limit=100) == ids

    def test_list_vectors_carries_metadata_and_vectors_only_on_request(
        self, adapter, test_collection_name, test_dimension, sample_documents
    ):
        adapter.initialize()
        adapter.create_collection(test_collection_name, test_dimension)
        adapter.store_vectors(test_collection_name, sample_documents)

        light = {d.id: d for d in adapter.list_vectors(test_collection_name).documents}
        full = {
            d.id: d
            for d in adapter.list_vectors(
                test_collection_name, include_vectors=True
            ).documents
        }

        assert light["doc_1"].metadata == {"category": "cat_1", "index": 1}
        assert light["doc_1"].payload == {"data": "payload_1"}
        assert light["doc_1"].vector.size == 0
        np.testing.assert_array_almost_equal(
            full["doc_1"].vector, sample_documents[1].vector, decimal=5
        )

    def test_list_vectors_of_an_empty_collection(
        self, adapter, test_collection_name, test_dimension
    ):
        adapter.initialize()
        adapter.create_collection(test_collection_name, test_dimension)

        page = adapter.list_vectors(test_collection_name)

        assert page.documents == []
        assert page.next_cursor is None

    def test_collection_info_reports_dimension_metric_and_size(
        self, adapter, test_collection_name, test_dimension, sample_documents
    ):
        adapter.initialize()
        adapter.create_collection(
            test_collection_name, test_dimension, distance_metric="euclidean"
        )
        adapter.store_vectors(test_collection_name, sample_documents)

        info = adapter.get_collection_info(test_collection_name)

        assert info.name == test_collection_name
        assert info.dimension == test_dimension
        assert info.distance_metric == "euclidean"
        assert info.size == len(sample_documents)

    # ------------------------------------------------------------------
    # Streaming a whole collection (list_vectors_stream).
    # ------------------------------------------------------------------

    def _store_many(self, adapter, collection_name, dimension, count=1_100):
        rng = np.random.default_rng(7)
        documents = [
            VectorDocument(
                id=f"many_{i:05d}",
                vector=rng.standard_normal(dimension).astype(np.float32),
                metadata={"index": i},
                payload={"text": f"row {i}"},
            )
            for i in range(count)
        ]
        for start in range(0, count, 250):  # small requests, whatever the adapter
            adapter.store_vectors(collection_name, documents[start : start + 250])
        return documents

    def test_list_vectors_stream_reads_every_document_in_list_order(
        self, adapter, test_collection_name, test_dimension
    ):
        adapter.initialize()
        adapter.create_collection(test_collection_name, test_dimension)
        documents = self._store_many(adapter, test_collection_name, test_dimension)

        with adapter.list_vectors_stream(
            test_collection_name, include_vectors=True
        ) as stream:
            streamed = list(stream)

        assert [d.id for d in streamed] == self._walk(
            adapter, test_collection_name, limit=100
        )
        assert len(streamed) == len(documents)
        by_id = {d.id: d for d in streamed}
        np.testing.assert_array_almost_equal(
            by_id["many_00042"].vector, documents[42].vector, decimal=5
        )
        assert by_id["many_00042"].metadata == {"index": 42}
        assert by_id["many_00042"].payload == {"text": "row 42"}

    def test_list_vectors_stream_carries_vectors_only_on_request(
        self, adapter, test_collection_name, test_dimension, sample_documents
    ):
        adapter.initialize()
        adapter.create_collection(test_collection_name, test_dimension)
        adapter.store_vectors(test_collection_name, sample_documents)

        with adapter.list_vectors_stream(test_collection_name) as stream:
            light = list(stream)

        assert sorted(d.id for d in light) == sorted(d.id for d in sample_documents)
        assert all(d.vector.size == 0 for d in light)

    def test_list_vectors_stream_of_an_empty_collection(
        self, adapter, test_collection_name, test_dimension
    ):
        adapter.initialize()
        adapter.create_collection(test_collection_name, test_dimension)

        with adapter.list_vectors_stream(test_collection_name) as stream:
            assert list(stream) == []

    def test_leaving_a_list_vectors_stream_early_releases_it(
        self, adapter, test_collection_name, test_dimension
    ):
        adapter.initialize()
        adapter.create_collection(test_collection_name, test_dimension)
        self._store_many(adapter, test_collection_name, test_dimension)

        with adapter.list_vectors_stream(test_collection_name) as stream:
            first = [next(stream) for _ in range(3)]

        assert len({d.id for d in first}) == 3
        with adapter.list_vectors_stream(test_collection_name) as stream:
            assert sum(1 for _ in stream) == 1_100

    def test_integers_in_metadata_and_payload_keep_their_type_and_value(
        self, adapter, test_collection_name, test_dimension, sample_vectors
    ):
        # JSON values, exact on every adapter and over NATS (no doubles).
        big = 2**60 + 1
        metadata = {"index": 3, "big": big, "nested": {"n": 42, "items": [1, 2.5]}}
        payload = {"count": 7, "big": big, "flag": True, "none": None}
        adapter.initialize()
        adapter.create_collection(test_collection_name, test_dimension)
        adapter.store_vectors(
            test_collection_name,
            [
                VectorDocument(
                    id="exact",
                    vector=sample_vectors[0],
                    metadata=metadata,
                    payload=payload,
                ),
                VectorDocument(
                    id="other",
                    vector=sample_vectors[1],
                    metadata={"index": 4},
                    payload=None,
                ),
            ],
        )

        def exact(found_metadata, found_payload):
            assert found_metadata == metadata and found_payload == payload
            assert type(found_metadata["index"]) is int
            assert type(found_metadata["nested"]["n"]) is int
            assert type(found_payload["big"]) is int

        stored = adapter.get_vector(test_collection_name, "exact")
        exact(stored.metadata, stored.payload)
        assert adapter.get_vector(test_collection_name, "other").payload is None
        page = adapter.list_vectors(test_collection_name, limit=10)
        listed = {d.id: d for d in page.documents}
        exact(listed["exact"].metadata, listed["exact"].payload)
        with adapter.list_vectors_stream(test_collection_name) as stream:
            streamed = {d.id: d for d in stream}
        exact(streamed["exact"].metadata, streamed["exact"].payload)

        (hit,) = adapter.search(
            test_collection_name,
            sample_vectors[0],
            k=5,
            filter={"index": 3},
            include_metadata=True,
        )
        assert hit.id == "exact"
        exact(hit.metadata, hit.payload)

        adapter.update_vector(
            test_collection_name,
            "other",
            metadata={"index": 5, "big": big},
            payload={"count": 8},
        )
        updated = adapter.get_vector(test_collection_name, "other")
        assert updated.metadata == {"index": 5, "big": big}
        assert updated.payload == {"count": 8}
        assert type(updated.metadata["big"]) is int
