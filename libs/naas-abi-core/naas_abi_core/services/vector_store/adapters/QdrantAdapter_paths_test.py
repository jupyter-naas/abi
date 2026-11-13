"""The Qdrant adapter never puts a collection name that is not one identifier
into a request: qdrant-client formats it into URL paths unencoded."""

import numpy as np
import pytest
from naas_abi_core.services.vector_store.adapters.QdrantAdapter import QdrantAdapter
from naas_abi_core.services.vector_store.IVectorStorePort import (
    InvalidCollectionNameError,
    VectorDocument,
)


class _RecordingClient:
    """Stands in for qdrant-client: any call it receives is recorded."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def __getattr__(self, name):
        def record(*args, **kwargs):
            self.calls.append(name)

        return record


@pytest.mark.parametrize("name", ["evil_/../victim", "../victim", "a/b", ".x", ""])
def test_qdrant_adapter_keeps_collection_names_out_of_url_paths(name):
    adapter = QdrantAdapter()
    client = _RecordingClient()
    adapter.client = client  # type: ignore[assignment]
    vector = np.array([1.0, 0.0])

    for call in (
        lambda: adapter.create_collection(name, 2),
        lambda: adapter.delete_collection(name),
        lambda: adapter.search(name, vector, k=1),
        lambda: adapter.get_vector(name, "a"),
        lambda: adapter.store_vectors(name, [VectorDocument(id="a", vector=vector, metadata={})]),
        lambda: adapter.delete_vectors(name, ["a"]),
        lambda: adapter.count_vectors(name),
        lambda: adapter.get_collection_info(name),
    ):
        with pytest.raises(InvalidCollectionNameError):
            call()
    assert client.calls == []
