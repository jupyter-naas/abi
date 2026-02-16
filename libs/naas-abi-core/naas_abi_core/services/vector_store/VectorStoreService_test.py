import pytest
from unittest.mock import Mock
import numpy as np
from .VectorStoreService import VectorStoreService
from .IVectorStorePort import IVectorStorePort, VectorDocument, SearchResult


class TestVectorStoreService:
    @pytest.fixture
    def mock_adapter(self):
        adapter = Mock(spec=IVectorStorePort)
        adapter.initialize = Mock()
        adapter.list_collections = Mock(return_value=[])
        adapter.create_collection = Mock()
        adapter.delete_collection = Mock()
        adapter.store_vectors = Mock()
        adapter.search = Mock()
        adapter.get_vector = Mock()
        adapter.update_vector = Mock()
        adapter.delete_vectors = Mock()
        adapter.count_vectors = Mock()
        adapter.close = Mock()
        return adapter

    @pytest.fixture
    def service(self, mock_adapter):
        return VectorStoreService(mock_adapter)

    def test_initialize(self, service, mock_adapter):
        service.initialize()
        mock_adapter.initialize.assert_called_once()

        service.initialize()
        mock_adapter.initialize.assert_called_once()

    def test_ensure_collection_create_new(self, service, mock_adapter):
        mock_adapter.list_collections.return_value = []

        service.ensure_collection("test_collection", 128)

        mock_adapter.create_collection.assert_called_once_with(
            "test_collection", 128, "cosine"
        )

    def test_ensure_collection_exists_no_recreate(self, service, mock_adapter):
        mock_adapter.list_collections.return_value = ["test_collection"]

        service.ensure_collection("test_collection", 128, recreate=False)

        mock_adapter.create_collection.assert_not_called()
        mock_adapter.delete_collection.assert_not_called()

    def test_ensure_collection_recreate(self, service, mock_adapter):
        mock_adapter.list_collections.return_value = ["test_collection"]

        service.ensure_collection("test_collection", 128, recreate=True)

        mock_adapter.delete_collection.assert_called_once_with("test_collection")
        mock_adapter.create_collection.assert_called_once_with(
            "test_collection", 128, "cosine"
        )

    def test_add_documents(self, service, mock_adapter):
        ids = ["doc1", "doc2"]
        vectors = [np.random.randn(128), np.random.randn(128)]
        metadata = [{"key": "value1"}, {"key": "value2"}]

        service.add_documents("test_collection", ids, vectors, metadata)

        mock_adapter.store_vectors.assert_called_once()
        call_args = mock_adapter.store_vectors.call_args
        assert call_args[0][0] == "test_collection"
        assert len(call_args[0][1]) == 2
        assert call_args[0][1][0].id == "doc1"

    def test_add_documents_validation(self, service, mock_adapter):
        with pytest.raises(ValueError, match="IDs and vectors cannot be empty"):
            service.add_documents("test_collection", [], [])

        with pytest.raises(ValueError, match="Number of IDs must match"):
            service.add_documents(
                "test_collection",
                ["doc1"],
                [np.random.randn(128), np.random.randn(128)],
            )

    def test_search_similar(self, service, mock_adapter):
        mock_results = [
            SearchResult(id="doc1", score=0.95, metadata={"key": "value1"}),
            SearchResult(id="doc2", score=0.85, metadata={"key": "value2"}),
        ]
        mock_adapter.search.return_value = mock_results

        query_vector = np.random.randn(128)
        results = service.search_similar("test_collection", query_vector, k=5)

        assert len(results) == 2
        assert results[0].id == "doc1"
        mock_adapter.search.assert_called_once()

    def test_search_similar_with_threshold(self, service, mock_adapter):
        mock_results = [
            SearchResult(id="doc1", score=0.95),
            SearchResult(id="doc2", score=0.85),
            SearchResult(id="doc3", score=0.75),
        ]
        mock_adapter.search.return_value = mock_results

        query_vector = np.random.randn(128)
        results = service.search_similar(
            "test_collection", query_vector, k=5, score_threshold=0.8
        )

        assert len(results) == 2
        assert all(r.score >= 0.8 for r in results)

    def test_get_document(self, service, mock_adapter):
        mock_doc = VectorDocument(
            id="doc1", vector=np.random.randn(128), metadata={"key": "value"}
        )
        mock_adapter.get_vector.return_value = mock_doc

        doc = service.get_document("test_collection", "doc1")

        assert doc.id == "doc1"
        mock_adapter.get_vector.assert_called_once_with("test_collection", "doc1", True)

    def test_update_document(self, service, mock_adapter):
        new_metadata = {"key": "new_value"}

        service.update_document("test_collection", "doc1", metadata=new_metadata)

        mock_adapter.update_vector.assert_called_once_with(
            "test_collection", "doc1", None, new_metadata, None
        )

    def test_update_document_validation(self, service, mock_adapter):
        with pytest.raises(ValueError, match="At least one of"):
            service.update_document("test_collection", "doc1")

    def test_delete_documents(self, service, mock_adapter):
        service.delete_documents("test_collection", ["doc1", "doc2"])

        mock_adapter.delete_vectors.assert_called_once_with(
            "test_collection", ["doc1", "doc2"]
        )

    def test_delete_documents_validation(self, service, mock_adapter):
        with pytest.raises(ValueError, match="Document IDs cannot be empty"):
            service.delete_documents("test_collection", [])

    def test_get_collection_size(self, service, mock_adapter):
        mock_adapter.count_vectors.return_value = 42

        count = service.get_collection_size("test_collection")

        assert count == 42
        mock_adapter.count_vectors.assert_called_once_with("test_collection")

    def test_list_collections(self, service, mock_adapter):
        mock_adapter.list_collections.return_value = ["coll1", "coll2"]

        collections = service.list_collections()

        assert collections == ["coll1", "coll2"]

    def test_delete_collection(self, service, mock_adapter):
        service.delete_collection("test_collection")

        mock_adapter.delete_collection.assert_called_once_with("test_collection")

    def test_close(self, service, mock_adapter):
        service.initialize()
        service.close()

        mock_adapter.close.assert_called_once()
        assert not service._initialized
