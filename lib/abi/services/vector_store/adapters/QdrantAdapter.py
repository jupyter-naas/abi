import logging
from typing import List, Dict, Any, Optional
import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    UpdateStatus,
    PointVectors,
)
from ..IVectorStorePort import IVectorStorePort, VectorDocument, SearchResult

logger = logging.getLogger(__name__)


class QdrantAdapter(IVectorStorePort):
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6333,
        api_key: Optional[str] = None,
        https: bool = False,
        timeout: int = 30
    ):
        self.host = host
        self.port = port
        self.api_key = api_key
        self.https = https
        self.timeout = timeout
        self.client: Optional[QdrantClient] = None

    def initialize(self) -> None:
        if self.client is None:
            self.client = QdrantClient(
                host=self.host,
                port=self.port,
                api_key=self.api_key,
                https=self.https,
                timeout=self.timeout
            )
            logger.info(f"Connected to Qdrant at {self.host}:{self.port}")

    def _get_distance_metric(self, metric: str) -> Distance:
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
        **kwargs
    ) -> None:
        if not self.client:
            raise RuntimeError("Adapter not initialized")
        
        self.client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(
                size=dimension,
                distance=self._get_distance_metric(distance_metric)
            ),
            **kwargs
        )
        logger.info(f"Created collection: {collection_name}")

    def delete_collection(self, collection_name: str) -> None:
        if not self.client:
            raise RuntimeError("Adapter not initialized")
        
        self.client.delete_collection(collection_name=collection_name)
        logger.info(f"Deleted collection: {collection_name}")

    def list_collections(self) -> List[str]:
        if not self.client:
            raise RuntimeError("Adapter not initialized")
        
        collections = self.client.get_collections()
        return [c.name for c in collections.collections]

    def store_vectors(
        self,
        collection_name: str,
        documents: List[VectorDocument]
    ) -> None:
        if not self.client:
            raise RuntimeError("Adapter not initialized")
        
        points = []
        for doc in documents:
            payload = {}
            if doc.metadata:
                payload.update(doc.metadata)
            if doc.payload:
                payload["payload"] = doc.payload
            
            point = PointStruct(
                id=doc.id,
                vector=doc.vector.tolist(),
                payload=payload if payload else None
            )
            points.append(point)
        
        operation_info = self.client.upsert(
            collection_name=collection_name,
            points=points
        )
        
        if operation_info.status != UpdateStatus.COMPLETED:
            raise RuntimeError(f"Failed to store vectors: {operation_info}")
        
        logger.debug(f"Stored {len(documents)} vectors in {collection_name}")

    def search(
        self,
        collection_name: str,
        query_vector: np.ndarray,
        k: int = 10,
        filter: Optional[Dict[str, Any]] = None,
        include_vectors: bool = False,
        include_metadata: bool = True
    ) -> List[SearchResult]:
        if not self.client:
            raise RuntimeError("Adapter not initialized")
        
        search_filter = None
        if filter:
            conditions = []
            for key, value in filter.items():
                conditions.append(
                    FieldCondition(
                        key=key,
                        match=MatchValue(value=value)
                    )
                )
            if conditions:
                from typing import cast
                search_filter = Filter(must=cast(Any, conditions))
        
        search_result = self.client.query_points(
            collection_name=collection_name,
            query=query_vector.tolist(),
            limit=k,
            query_filter=search_filter,
            with_vectors=include_vectors,
            with_payload=include_metadata
        )
        
        results = []
        for hit in search_result.points:
            result = SearchResult(
                id=str(hit.id),
                score=hit.score,
                vector=np.array(hit.vector) if hit.vector else None,
                metadata=dict(hit.payload) if hit.payload and include_metadata else None,
                payload=hit.payload.get("payload") if hit.payload and "payload" in hit.payload else None
            )
            results.append(result)
        
        return results

    def get_vector(
        self,
        collection_name: str,
        vector_id: str,
        include_vector: bool = True
    ) -> Optional[VectorDocument]:
        if not self.client:
            raise RuntimeError("Adapter not initialized")
        
        points = self.client.retrieve(
            collection_name=collection_name,
            ids=[vector_id],
            with_vectors=include_vector,
            with_payload=True
        )
        
        if not points:
            return None
        
        point = points[0]
        payload = dict(point.payload) if point.payload else {}
        
        vector_array = np.array(point.vector) if point.vector else np.array([])
        return VectorDocument(
            id=str(point.id),
            vector=vector_array,
            metadata={k: v for k, v in payload.items() if k != "payload"},
            payload=payload.get("payload")
        )

    def update_vector(
        self,
        collection_name: str,
        vector_id: str,
        vector: Optional[np.ndarray] = None,
        metadata: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None
    ) -> None:
        if not self.client:
            raise RuntimeError("Adapter not initialized")
        
        if vector is not None:
            self.client.update_vectors(
                collection_name=collection_name,
                points=[
                    PointVectors(
                        id=vector_id,
                        vector=vector.tolist()
                    )
                ]
            )
        
        if metadata is not None or payload is not None:
            new_payload = {}
            if metadata:
                new_payload.update(metadata)
            if payload:
                new_payload["payload"] = payload
            
            self.client.set_payload(
                collection_name=collection_name,
                payload=new_payload,
                points=[vector_id]
            )

    def delete_vectors(
        self,
        collection_name: str,
        vector_ids: List[str]
    ) -> None:
        if not self.client:
            raise RuntimeError("Adapter not initialized")
        
        self.client.delete(
            collection_name=collection_name,
            points_selector=vector_ids
        )
        logger.debug(f"Deleted {len(vector_ids)} vectors from {collection_name}")

    def count_vectors(self, collection_name: str) -> int:
        if not self.client:
            raise RuntimeError("Adapter not initialized")
        
        collection_info = self.client.get_collection(collection_name=collection_name)
        return collection_info.indexed_vectors_count or 0

    def close(self) -> None:
        if self.client:
            self.client.close()
            self.client = None
            logger.info("Closed connection to Qdrant")