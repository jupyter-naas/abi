import numpy as np
import pytest

from ..IVectorStorePort import VectorDocument
from ..IVectorStorePort_test import GenericVectorStoreAdapterTest
from .SqliteVecAdapter import SqliteVecAdapter

pytest.importorskip("sqlite_vec")


class TestSqliteVecAdapter(GenericVectorStoreAdapterTest):
    @pytest.fixture
    def adapter(self, tmp_path):
        adapter = SqliteVecAdapter(str(tmp_path / "vectors.db"))
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
