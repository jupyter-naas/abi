import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np

from ..IVectorStorePort import IVectorStorePort, SearchResult, VectorDocument

logger = logging.getLogger(__name__)


@dataclass
class _InMemoryCollection:
    dimension: int
    distance_metric: str
    documents: Dict[str, VectorDocument] = field(default_factory=dict)


class QdrantInMemoryAdapter(IVectorStorePort):
    def __init__(self) -> None:
        self._collections: Dict[str, _InMemoryCollection] = {}
        self._initialized = False

    def initialize(self) -> None:
        self._initialized = True
        logger.info("Initialized QdrantInMemoryAdapter")

    def _require_initialized(self) -> None:
        if not self._initialized:
            raise RuntimeError("Adapter not initialized")

    def _get_collection(self, collection_name: str) -> _InMemoryCollection:
        collection = self._collections.get(collection_name)
        if collection is None:
            raise KeyError(f"Collection not found: {collection_name}")
        return collection

    def _to_vector(self, vector: np.ndarray) -> np.ndarray:
        array = np.asarray(vector, dtype=float)
        if array.ndim != 1:
            array = array.reshape(-1)
        return array

    def _validate_dimension(
        self, collection: _InMemoryCollection, vector: np.ndarray
    ) -> None:
        if vector.size != collection.dimension:
            raise ValueError(
                "Vector dimension mismatch. "
                f"Expected {collection.dimension}, got {vector.size}"
            )

    def _score(
        self, metric: str, query_vector: np.ndarray, candidate_vector: np.ndarray
    ) -> float:
        metric_key = metric.lower()
        if metric_key == "euclidean":
            return float(-np.linalg.norm(query_vector - candidate_vector))
        if metric_key == "dot":
            return float(np.dot(query_vector, candidate_vector))

        query_norm = np.linalg.norm(query_vector)
        candidate_norm = np.linalg.norm(candidate_vector)
        if query_norm == 0.0 or candidate_norm == 0.0:
            return 0.0
        return float(np.dot(query_vector, candidate_vector) / (query_norm * candidate_norm))

    def _matches_filter(
        self, document: VectorDocument, filter: Optional[Dict[str, Any]]
    ) -> bool:
        if not filter:
            return True

        payload: Dict[str, Any] = {}
        if document.metadata:
            payload.update(document.metadata)
        if document.payload is not None:
            payload["payload"] = document.payload

        for key, value in filter.items():
            if key not in payload or payload[key] != value:
                return False
        return True

    def create_collection(
        self,
        collection_name: str,
        dimension: int,
        distance_metric: str = "cosine",
        **kwargs,
    ) -> None:
        self._require_initialized()

        if collection_name in self._collections:
            raise RuntimeError(f"Collection already exists: {collection_name}")

        self._collections[collection_name] = _InMemoryCollection(
            dimension=dimension, distance_metric=distance_metric
        )
        logger.info(f"Created collection: {collection_name}")

    def delete_collection(self, collection_name: str) -> None:
        self._require_initialized()

        if collection_name in self._collections:
            del self._collections[collection_name]
            logger.info(f"Deleted collection: {collection_name}")
            return

        raise KeyError(f"Collection not found: {collection_name}")

    def list_collections(self) -> List[str]:
        self._require_initialized()
        return list(self._collections.keys())

    def store_vectors(
        self, collection_name: str, documents: List[VectorDocument]
    ) -> None:
        self._require_initialized()

        collection = self._get_collection(collection_name)

        for doc in documents:
            vector = self._to_vector(doc.vector)
            self._validate_dimension(collection, vector)

            collection.documents[doc.id] = VectorDocument(
                id=doc.id,
                vector=vector.copy(),
                metadata=dict(doc.metadata) if doc.metadata else {},
                payload=dict(doc.payload) if doc.payload is not None else None,
            )

        logger.debug(f"Stored {len(documents)} vectors in {collection_name}")

    def search(
        self,
        collection_name: str,
        query_vector: np.ndarray,
        k: int = 10,
        filter: Optional[Dict[str, Any]] = None,
        include_vectors: bool = False,
        include_metadata: bool = True,
    ) -> List[SearchResult]:
        self._require_initialized()

        collection = self._get_collection(collection_name)
        query_array = self._to_vector(query_vector)
        self._validate_dimension(collection, query_array)

        results: List[SearchResult] = []
        for doc in collection.documents.values():
            if not self._matches_filter(doc, filter):
                continue

            score = self._score(collection.distance_metric, query_array, doc.vector)
            results.append(
                SearchResult(
                    id=doc.id,
                    score=score,
                    vector=doc.vector.copy() if include_vectors else None,
                    metadata=dict(doc.metadata) if include_metadata else None,
                    payload=(
                        dict(doc.payload)
                        if include_metadata and doc.payload is not None
                        else None
                    ),
                )
            )

        results.sort(key=lambda item: item.score, reverse=True)
        return results[:k]

    def get_vector(
        self, collection_name: str, vector_id: str, include_vector: bool = True
    ) -> Optional[VectorDocument]:
        self._require_initialized()

        collection = self._get_collection(collection_name)
        doc = collection.documents.get(vector_id)
        if doc is None:
            return None

        return VectorDocument(
            id=doc.id,
            vector=doc.vector.copy() if include_vector else np.array([]),
            metadata=dict(doc.metadata) if doc.metadata else {},
            payload=dict(doc.payload) if doc.payload is not None else None,
        )

    def update_vector(
        self,
        collection_name: str,
        vector_id: str,
        vector: Optional[np.ndarray] = None,
        metadata: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        self._require_initialized()

        collection = self._get_collection(collection_name)
        doc = collection.documents.get(vector_id)
        if doc is None:
            raise KeyError(f"Vector not found: {vector_id}")

        if vector is not None:
            new_vector = self._to_vector(vector)
            self._validate_dimension(collection, new_vector)
            doc.vector = new_vector.copy()

        if metadata is not None:
            doc.metadata = dict(metadata)

        if payload is not None:
            doc.payload = dict(payload)

    def delete_vectors(self, collection_name: str, vector_ids: List) -> None:
        self._require_initialized()

        collection = self._get_collection(collection_name)
        for vector_id in vector_ids:
            collection.documents.pop(vector_id, None)

        logger.debug(f"Deleted {len(vector_ids)} vectors from {collection_name}")

    def count_vectors(self, collection_name: str) -> int:
        self._require_initialized()
        collection = self._get_collection(collection_name)
        return len(collection.documents)

    def close(self) -> None:
        self._initialized = False
        logger.info("Closed QdrantInMemoryAdapter")
