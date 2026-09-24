import numpy as np
import pytest
from naas_abi_core.services.vector_store.adapters.SqliteVecAdapter import (
    SqliteVecAdapter,
)
from naas_abi_core.services.vector_store.IVectorStorePort import VectorDocument
from naas_abi_core.services.vector_store.IVectorStorePort_test import (
    GenericVectorStoreAdapterTest,
)


class TestSqliteVecAdapter(GenericVectorStoreAdapterTest):
    @pytest.fixture
    def adapter(self, tmp_path):
        adapter = SqliteVecAdapter(persistence_path=str(tmp_path / "vectors.sqlite3"))
        adapter.initialize()
        yield adapter
        adapter.close()

    @pytest.mark.parametrize("metric", ["cosine", "dot"])
    def test_cosine_scores_are_similarities(self, adapter, metric):
        """Like the Qdrant adapters: 1 for the same direction, 0 orthogonal,
        -1 opposite, so higher is better and ``score_threshold`` works."""
        adapter.create_collection("scores", 2, distance_metric=metric)
        adapter.store_vectors(
            "scores",
            [
                VectorDocument(id="same", vector=np.array([2.0, 0.0]), metadata={}),
                VectorDocument(
                    id="orthogonal", vector=np.array([0.0, 1.0]), metadata={}
                ),
                VectorDocument(
                    id="opposite", vector=np.array([-1.0, 0.0]), metadata={}
                ),
            ],
        )
        results = adapter.search("scores", np.array([1.0, 0.0]), k=3)
        scores = {r.id: r.score for r in results}
        assert [r.id for r in results] == ["same", "orthogonal", "opposite"]
        assert scores["same"] == pytest.approx(1.0, abs=1e-5)
        assert scores["orthogonal"] == pytest.approx(0.0, abs=1e-5)
        assert scores["opposite"] == pytest.approx(-1.0, abs=1e-5)
