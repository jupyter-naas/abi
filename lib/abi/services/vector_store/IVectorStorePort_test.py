import pytest
import numpy as np
from typing import List
from abc import ABC
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
    def sample_vectors(self) -> List[np.ndarray]:
        np.random.seed(42)
        return [
            np.random.randn(128).astype(np.float32) for _ in range(5)
        ]

    @pytest.fixture
    def sample_documents(self, sample_vectors) -> List[VectorDocument]:
        return [
            VectorDocument(
                id=f"doc_{i}",
                vector=vector,
                metadata={"category": f"cat_{i % 2}", "index": i},
                payload={"data": f"payload_{i}"}
            )
            for i, vector in enumerate(sample_vectors)
        ]

    @pytest.mark.asyncio
    async def test_initialize(self, adapter):
        await adapter.initialize()
        assert True

    @pytest.mark.asyncio
    async def test_create_and_list_collections(
        self, adapter, test_collection_name, test_dimension
    ):
        await adapter.initialize()
        
        await adapter.create_collection(
            test_collection_name, test_dimension, distance_metric="cosine"
        )
        
        collections = await adapter.list_collections()
        assert test_collection_name in collections

    @pytest.mark.asyncio
    async def test_store_and_retrieve_vectors(
        self, adapter, test_collection_name, test_dimension, sample_documents
    ):
        await adapter.initialize()
        
        await adapter.create_collection(test_collection_name, test_dimension)
        
        await adapter.store_vectors(test_collection_name, sample_documents)
        
        retrieved = await adapter.get_vector(
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

    @pytest.mark.asyncio
    async def test_search_vectors(
        self, adapter, test_collection_name, test_dimension, sample_documents
    ):
        await adapter.initialize()
        
        await adapter.create_collection(test_collection_name, test_dimension)
        await adapter.store_vectors(test_collection_name, sample_documents)
        
        query_vector = sample_documents[0].vector
        results = await adapter.search(
            test_collection_name,
            query_vector,
            k=3,
            include_metadata=True
        )
        
        assert len(results) <= 3
        assert results[0].id == "doc_0"
        assert results[0].score >= 0.99

    @pytest.mark.asyncio
    async def test_search_with_filter(
        self, adapter, test_collection_name, test_dimension, sample_documents
    ):
        await adapter.initialize()
        
        await adapter.create_collection(test_collection_name, test_dimension)
        await adapter.store_vectors(test_collection_name, sample_documents)
        
        query_vector = sample_documents[0].vector
        results = await adapter.search(
            test_collection_name,
            query_vector,
            k=10,
            filter={"category": "cat_0"},
            include_metadata=True
        )
        
        for result in results:
            assert result.metadata["category"] == "cat_0"

    @pytest.mark.asyncio
    async def test_update_vector(
        self, adapter, test_collection_name, test_dimension, sample_documents
    ):
        await adapter.initialize()
        
        await adapter.create_collection(test_collection_name, test_dimension)
        await adapter.store_vectors(test_collection_name, [sample_documents[0]])
        
        new_metadata = {"category": "updated", "new_field": "value"}
        await adapter.update_vector(
            test_collection_name,
            "doc_0",
            metadata=new_metadata
        )
        
        retrieved = await adapter.get_vector(test_collection_name, "doc_0")
        assert retrieved.metadata["category"] == "updated"
        assert retrieved.metadata["new_field"] == "value"

    @pytest.mark.asyncio
    async def test_delete_vectors(
        self, adapter, test_collection_name, test_dimension, sample_documents
    ):
        await adapter.initialize()
        
        await adapter.create_collection(test_collection_name, test_dimension)
        await adapter.store_vectors(test_collection_name, sample_documents)
        
        initial_count = await adapter.count_vectors(test_collection_name)
        assert initial_count == len(sample_documents)
        
        await adapter.delete_vectors(test_collection_name, ["doc_0", "doc_1"])
        
        final_count = await adapter.count_vectors(test_collection_name)
        assert final_count == initial_count - 2
        
        deleted_doc = await adapter.get_vector(test_collection_name, "doc_0")
        assert deleted_doc is None

    @pytest.mark.asyncio
    async def test_count_vectors(
        self, adapter, test_collection_name, test_dimension, sample_documents
    ):
        await adapter.initialize()
        
        await adapter.create_collection(test_collection_name, test_dimension)
        
        count_empty = await adapter.count_vectors(test_collection_name)
        assert count_empty == 0
        
        await adapter.store_vectors(test_collection_name, sample_documents)
        
        count_filled = await adapter.count_vectors(test_collection_name)
        assert count_filled == len(sample_documents)

    @pytest.mark.asyncio
    async def test_delete_collection(
        self, adapter, test_collection_name, test_dimension
    ):
        await adapter.initialize()
        
        await adapter.create_collection(test_collection_name, test_dimension)
        
        collections_before = await adapter.list_collections()
        assert test_collection_name in collections_before
        
        await adapter.delete_collection(test_collection_name)
        
        collections_after = await adapter.list_collections()
        assert test_collection_name not in collections_after

    @pytest.mark.asyncio
    async def test_close(self, adapter):
        await adapter.initialize()
        await adapter.close()
        assert True