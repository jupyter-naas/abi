import logging
from typing import List, Dict, Any, Optional
import numpy as np
from .IVectorStorePort import IVectorStorePort, VectorDocument, SearchResult

logger = logging.getLogger(__name__)


class VectorStoreService:
    def __init__(self, adapter: IVectorStorePort):
        self.adapter = adapter
        self._initialized = False

    async def initialize(self) -> None:
        if not self._initialized:
            await self.adapter.initialize()
            self._initialized = True
            logger.info("VectorStoreService initialized successfully")

    async def ensure_collection(
        self,
        collection_name: str,
        dimension: int,
        distance_metric: str = "cosine",
        recreate: bool = False,
        **kwargs
    ) -> None:
        await self.initialize()
        
        existing_collections = await self.adapter.list_collections()
        
        if collection_name in existing_collections:
            if recreate:
                logger.info(f"Recreating collection: {collection_name}")
                await self.adapter.delete_collection(collection_name)
                await self.adapter.create_collection(
                    collection_name, dimension, distance_metric, **kwargs
                )
            else:
                logger.debug(f"Collection {collection_name} already exists")
        else:
            logger.info(f"Creating new collection: {collection_name}")
            await self.adapter.create_collection(
                collection_name, dimension, distance_metric, **kwargs
            )

    async def add_documents(
        self,
        collection_name: str,
        ids: List[str],
        vectors: List[np.ndarray],
        metadata: Optional[List[Dict[str, Any]]] = None,
        payloads: Optional[List[Dict[str, Any]]] = None
    ) -> None:
        await self.initialize()
        
        if not ids or not vectors:
            raise ValueError("IDs and vectors cannot be empty")
        
        if len(ids) != len(vectors):
            raise ValueError("Number of IDs must match number of vectors")
        
        if metadata and len(metadata) != len(ids):
            raise ValueError("Number of metadata entries must match number of IDs")
        
        if payloads and len(payloads) != len(ids):
            raise ValueError("Number of payloads must match number of IDs")
        
        documents = []
        for i, (doc_id, vector) in enumerate(zip(ids, vectors)):
            doc = VectorDocument(
                id=doc_id,
                vector=vector,
                metadata=metadata[i] if metadata else {},
                payload=payloads[i] if payloads else None
            )
            documents.append(doc)
        
        await self.adapter.store_vectors(collection_name, documents)
        logger.debug(f"Added {len(documents)} documents to collection {collection_name}")

    async def search_similar(
        self,
        collection_name: str,
        query_vector: np.ndarray,
        k: int = 10,
        filter: Optional[Dict[str, Any]] = None,
        score_threshold: Optional[float] = None,
        include_vectors: bool = False,
        include_metadata: bool = True
    ) -> List[SearchResult]:
        await self.initialize()
        
        if k <= 0:
            raise ValueError("k must be a positive integer")
        
        results = await self.adapter.search(
            collection_name=collection_name,
            query_vector=query_vector,
            k=k,
            filter=filter,
            include_vectors=include_vectors,
            include_metadata=include_metadata
        )
        
        if score_threshold is not None:
            results = [r for r in results if r.score >= score_threshold]
        
        logger.debug(f"Found {len(results)} similar vectors in {collection_name}")
        return results

    async def get_document(
        self,
        collection_name: str,
        document_id: str,
        include_vector: bool = True
    ) -> Optional[VectorDocument]:
        await self.initialize()
        return await self.adapter.get_vector(
            collection_name, document_id, include_vector
        )

    async def update_document(
        self,
        collection_name: str,
        document_id: str,
        vector: Optional[np.ndarray] = None,
        metadata: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None
    ) -> None:
        await self.initialize()
        
        if vector is None and metadata is None and payload is None:
            raise ValueError("At least one of vector, metadata, or payload must be provided")
        
        await self.adapter.update_vector(
            collection_name, document_id, vector, metadata, payload
        )
        logger.debug(f"Updated document {document_id} in collection {collection_name}")

    async def delete_documents(
        self,
        collection_name: str,
        document_ids: List[str]
    ) -> None:
        await self.initialize()
        
        if not document_ids:
            raise ValueError("Document IDs cannot be empty")
        
        await self.adapter.delete_vectors(collection_name, document_ids)
        logger.info(f"Deleted {len(document_ids)} documents from collection {collection_name}")

    async def get_collection_size(self, collection_name: str) -> int:
        await self.initialize()
        return await self.adapter.count_vectors(collection_name)

    async def list_collections(self) -> List[str]:
        await self.initialize()
        return await self.adapter.list_collections()

    async def delete_collection(self, collection_name: str) -> None:
        await self.initialize()
        await self.adapter.delete_collection(collection_name)
        logger.info(f"Deleted collection: {collection_name}")

    async def close(self) -> None:
        if self._initialized:
            await self.adapter.close()
            self._initialized = False
            logger.info("VectorStoreService closed")