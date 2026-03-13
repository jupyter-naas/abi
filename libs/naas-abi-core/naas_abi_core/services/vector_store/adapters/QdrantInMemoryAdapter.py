import logging
import os
import threading
from typing import Any, Dict, List, Optional, Union, cast
import uuid
from uuid import UUID

import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointIdsList,
    PointStruct,
    PointVectors,
    UpdateStatus,
    VectorParams,
)

from ..IVectorStorePort import IVectorStorePort, SearchResult, VectorDocument

logger = logging.getLogger(__name__)


class QdrantInMemoryAdapter(IVectorStorePort):
    """Local Qdrant adapter.

    Uses embedded Qdrant mode for both ephemeral (`:memory:`) and durable
    filesystem-backed persistence.
    """

    def __init__(
        self,
        storage_path: str = ":memory:",
        timeout: int = 300,
    ) -> None:
        self.storage_path = storage_path
        self.timeout = timeout
        self.client: Optional[QdrantClient] = None
        self._lock = threading.RLock()

    def initialize(self) -> None:
        with self._lock:
            if self.client is not None:
                return

            if self.storage_path == ":memory:":
                self.client = QdrantClient(location=":memory:", timeout=self.timeout)
                logger.info("Initialized in-memory local Qdrant")
                return

            os.makedirs(self.storage_path, exist_ok=True)
            self.client = QdrantClient(path=self.storage_path, timeout=self.timeout)
            logger.info("Initialized local Qdrant at %s", self.storage_path)

    def _require_initialized(self) -> QdrantClient:
        if self.client is None:
            raise RuntimeError("Adapter not initialized")
        return self.client

    @staticmethod
    def _point_id(vector_id: str) -> str:
        return str(uuid.uuid5(uuid.NAMESPACE_URL, vector_id))

    @staticmethod
    def _get_distance_metric(metric: str) -> Distance:
        metric_map = {
            "cosine": Distance.COSINE,
            "euclidean": Distance.EUCLID,
            "dot": Distance.DOT,
        }
        return metric_map.get(metric.lower(), Distance.COSINE)

    def create_collection(
        self,
        collection_name: str,
        dimension: int,
        distance_metric: str = "cosine",
        **kwargs,
    ) -> None:
        with self._lock:
            client = self._require_initialized()
            client.create_collection(
                collection_name=collection_name,
                vectors_config=VectorParams(
                    size=dimension, distance=self._get_distance_metric(distance_metric)
                ),
                **kwargs,
            )

    def delete_collection(self, collection_name: str) -> None:
        with self._lock:
            client = self._require_initialized()
            client.delete_collection(collection_name=collection_name)

    def list_collections(self) -> List[str]:
        with self._lock:
            client = self._require_initialized()
            collections = client.get_collections()
            return [c.name for c in collections.collections]

    def store_vectors(
        self, collection_name: str, documents: List[VectorDocument]
    ) -> None:
        with self._lock:
            client = self._require_initialized()
            points = []
            for doc in documents:
                payload = {}
                if doc.metadata:
                    payload.update(doc.metadata)
                if doc.payload:
                    payload["payload"] = doc.payload
                payload["_abi_id"] = doc.id
                payload["_abi_vector"] = doc.vector.tolist()

                points.append(
                    PointStruct(
                        id=self._point_id(doc.id),
                        vector=doc.vector.tolist(),
                        payload=payload,
                    )
                )

            operation_info = client.upsert(
                collection_name=collection_name, points=points
            )
            if operation_info.status != UpdateStatus.COMPLETED:
                raise RuntimeError(f"Failed to store vectors: {operation_info}")

    def search(
        self,
        collection_name: str,
        query_vector: np.ndarray,
        k: int = 10,
        filter: Optional[Dict[str, Any]] = None,
        include_vectors: bool = False,
        include_metadata: bool = True,
    ) -> List[SearchResult]:
        with self._lock:
            client = self._require_initialized()

            search_filter = None
            if filter:
                conditions = [
                    FieldCondition(key=key, match=MatchValue(value=value))
                    for key, value in filter.items()
                ]
                if conditions:
                    search_filter = Filter(must=cast(Any, conditions))

            search_result = client.query_points(
                collection_name=collection_name,
                query=query_vector.tolist(),
                limit=k,
                query_filter=search_filter,
                with_vectors=include_vectors,
                with_payload=include_metadata,
            )

            return [
                SearchResult(
                    id=str(hit.payload.get("_abi_id", hit.id))
                    if hit.payload
                    else str(hit.id),
                    score=hit.score,
                    vector=(
                        np.array(hit.payload["_abi_vector"])
                        if include_vectors
                        and hit.payload
                        and "_abi_vector" in hit.payload
                        else (
                            np.array(hit.vector)
                            if include_vectors and hit.vector is not None
                            else None
                        )
                    ),
                    metadata={
                        k: v
                        for k, v in dict(hit.payload).items()
                        if k not in {"payload", "_abi_id", "_abi_vector"}
                    }
                    if hit.payload and include_metadata
                    else None,
                    payload=hit.payload.get("payload")
                    if hit.payload and "payload" in hit.payload
                    else None,
                )
                for hit in search_result.points
            ]

    def get_vector(
        self, collection_name: str, vector_id: str, include_vector: bool = True
    ) -> Optional[VectorDocument]:
        with self._lock:
            client = self._require_initialized()
            points = client.retrieve(
                collection_name=collection_name,
                ids=[self._point_id(vector_id)],
                with_vectors=include_vector,
                with_payload=True,
            )

            if not points:
                return None

            point = points[0]
            payload = dict(point.payload) if point.payload else {}
            vector_array = (
                np.array(payload["_abi_vector"])
                if include_vector and "_abi_vector" in payload
                else (
                    np.array(point.vector)
                    if include_vector and point.vector is not None
                    else np.array([])
                )
            )
            return VectorDocument(
                id=str(payload.get("_abi_id", vector_id)),
                vector=vector_array,
                metadata={
                    k: v
                    for k, v in payload.items()
                    if k not in {"payload", "_abi_id", "_abi_vector"}
                },
                payload=payload.get("payload"),
            )

    def update_vector(
        self,
        collection_name: str,
        vector_id: str,
        vector: Optional[np.ndarray] = None,
        metadata: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None,
    ) -> None:
        with self._lock:
            client = self._require_initialized()

            if vector is not None:
                client.update_vectors(
                    collection_name=collection_name,
                    points=[
                        PointVectors(
                            id=self._point_id(vector_id),
                            vector=vector.tolist(),
                        )
                    ],
                )

            if metadata is not None or payload is not None or vector is not None:
                new_payload = {}
                if metadata:
                    new_payload.update(metadata)
                if payload:
                    new_payload["payload"] = payload
                new_payload["_abi_id"] = vector_id
                if vector is not None:
                    new_payload["_abi_vector"] = vector.tolist()

                client.set_payload(
                    collection_name=collection_name,
                    payload=new_payload,
                    points=[self._point_id(vector_id)],
                )

    def delete_vectors(self, collection_name: str, vector_ids: List[str]) -> None:
        with self._lock:
            client = self._require_initialized()
            point_ids = cast(
                List[Union[int, str, UUID]],
                [self._point_id(vector_id) for vector_id in vector_ids],
            )
            client.delete(
                collection_name=collection_name,
                points_selector=PointIdsList(points=point_ids),
            )

    def count_vectors(self, collection_name: str) -> int:
        with self._lock:
            client = self._require_initialized()
            collection_info = client.get_collection(collection_name=collection_name)
            return collection_info.points_count or 0

    def close(self) -> None:
        with self._lock:
            if self.client is not None:
                self.client.close()
                self.client = None
