from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pytest

from naas_abi_core.services.vector_store.IVectorStorePort import VectorDocument
from naas_abi_core.services.vector_store.IVectorStorePort_test import (
    GenericVectorStoreAdapterTest,
)
from naas_abi_core.services.vector_store.adapters.QdrantInMemoryAdapter import (
    QdrantInMemoryAdapter,
)


class TestQdrantInMemoryAdapter(GenericVectorStoreAdapterTest):
    @pytest.fixture
    def adapter(self):
        adapter = QdrantInMemoryAdapter(storage_path=":memory:")
        adapter.initialize()
        yield adapter
        adapter.close()

    def test_persistence_across_restart(self, tmp_path):
        storage_path = str(tmp_path / "qdrant-local")

        adapter = QdrantInMemoryAdapter(storage_path=storage_path)
        adapter.initialize()
        adapter.create_collection("persist", 4)
        adapter.store_vectors(
            "persist",
            [
                VectorDocument(
                    id="doc-1",
                    vector=np.array([0.1, 0.2, 0.3, 0.4], dtype=np.float32),
                    metadata={"kind": "test"},
                    payload={"v": 1},
                )
            ],
        )
        adapter.close()

        restarted = QdrantInMemoryAdapter(storage_path=storage_path)
        restarted.initialize()
        assert "persist" in restarted.list_collections()
        result = restarted.get_vector("persist", "doc-1")
        assert result is not None
        assert result.metadata["kind"] == "test"
        restarted.close()

    def test_concurrent_upsert_and_search(self, tmp_path):
        adapter = QdrantInMemoryAdapter(
            storage_path=str(tmp_path / "qdrant-concurrency")
        )
        adapter.initialize()
        adapter.create_collection("conc", 8)

        def _upsert(i: int) -> None:
            vector = np.ones(8, dtype=np.float32) * i
            adapter.store_vectors(
                "conc",
                [
                    VectorDocument(
                        id=f"doc-{i}",
                        vector=vector,
                        metadata={"i": i},
                        payload={"i": i},
                    )
                ],
            )

        with ThreadPoolExecutor(max_workers=8) as executor:
            list(executor.map(_upsert, range(30)))

        query = np.ones(8, dtype=np.float32) * 29
        results = adapter.search("conc", query, k=5)
        assert len(results) > 0
        assert adapter.count_vectors("conc") == 30
        adapter.close()
