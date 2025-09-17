import pytest
import os
from ..IVectorStorePort_test import GenericVectorStoreAdapterTest
from .QdrantAdapter import QdrantAdapter


@pytest.mark.skipif(
    os.getenv("QDRANT_HOST") is None,
    reason="Qdrant integration tests require QDRANT_HOST to be set"
)
class TestQdrantAdapter(GenericVectorStoreAdapterTest):
    @pytest.fixture
    async def adapter(self):
        adapter = QdrantAdapter(
            host=os.getenv("QDRANT_HOST", "localhost"),
            port=int(os.getenv("QDRANT_PORT", "6333")),
            api_key=os.getenv("QDRANT_API_KEY"),
            https=os.getenv("QDRANT_HTTPS", "false").lower() == "true"
        )
        
        await adapter.initialize()
        
        try:
            await adapter.delete_collection("test_collection")
        except Exception:
            pass
        
        yield adapter
        
        try:
            await adapter.delete_collection("test_collection")
        except Exception:
            pass
        
        await adapter.close()

    @pytest.mark.asyncio
    async def test_distance_metric_mapping(self):
        adapter = QdrantAdapter()
        
        from qdrant_client.models import Distance
        
        assert adapter._get_distance_metric("cosine") == Distance.COSINE
        assert adapter._get_distance_metric("euclidean") == Distance.EUCLID
        assert adapter._get_distance_metric("dot") == Distance.DOT
        assert adapter._get_distance_metric("unknown") == Distance.COSINE

    @pytest.mark.asyncio
    async def test_adapter_not_initialized_error(self):
        adapter = QdrantAdapter()
        
        with pytest.raises(RuntimeError, match="Adapter not initialized"):
            await adapter.create_collection("test", 128)
        
        with pytest.raises(RuntimeError, match="Adapter not initialized"):
            await adapter.list_collections()
        
        with pytest.raises(RuntimeError, match="Adapter not initialized"):
            await adapter.store_vectors("test", [])