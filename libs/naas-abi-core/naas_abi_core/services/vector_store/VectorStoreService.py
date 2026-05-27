import logging
from typing import Any, Dict, List, Optional

import numpy as np
from naas_abi_core import logger as abi_logger
from naas_abi_core.services.ServiceBase import ServiceBase
from naas_abi_core.services.vector_store.ontologies.modules.VectorStoreEventOntology import (
    CollectionDeleted,
    CollectionEnsured,
    DocumentsAdded,
    DocumentsDeleted,
    DocumentUpdated,
    VectorStoreError,
)

from .IVectorStorePort import IVectorStorePort, SearchResult, VectorDocument

logger = logging.getLogger(__name__)

class VectorStoreService(ServiceBase):
    def __init__(self, adapter: IVectorStorePort):
        super().__init__()
        self.adapter = adapter
        self._initialized = False

    def __publish_event(self, event: object) -> None:
        if not self.services_wired:
            return
        if not self.services.events_available():
            return
        try:
            self.services.events.publish(event)
        except Exception as exc:
            # Vector store is the source of truth; event logging must never break it.
            abi_logger.warning(
                f"VectorStoreService: failed to publish event: {exc}"
            )

    def initialize(self) -> None:
        if not self._initialized:
            self.adapter.initialize()
            self._initialized = True
            logger.info("VectorStoreService initialized successfully")

    def ensure_collection(
        self,
        collection_name: str,
        dimension: int,
        distance_metric: str = "cosine",
        recreate: bool = False,
        **kwargs
    ) -> None:
        self.initialize()

        try:
            existing_collections = self.adapter.list_collections()

            if collection_name in existing_collections:
                if recreate:
                    logger.info(f"Recreating collection: {collection_name}")
                    self.adapter.delete_collection(collection_name)
                    self.adapter.create_collection(
                        collection_name, dimension, distance_metric, **kwargs
                    )
                else:
                    logger.debug(f"Collection {collection_name} already exists")
            else:
                logger.info(f"Creating new collection: {collection_name}")
                self.adapter.create_collection(
                    collection_name, dimension, distance_metric, **kwargs
                )
        except Exception as exc:
            self.__publish_event(
                VectorStoreError(
                    collection_name=collection_name,
                    operation="ensure_collection",
                    message=str(exc),
                )
            )
            raise

        self.__publish_event(CollectionEnsured(collection_name=collection_name))

    def add_documents(
        self,
        collection_name: str,
        ids: List[str],
        vectors: List[np.ndarray],
        metadata: Optional[List[Dict[str, Any]]] = None,
        payloads: Optional[List[Dict[str, Any]]] = None
    ) -> None:
        self.initialize()

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

        try:
            self.adapter.store_vectors(collection_name, documents)
        except Exception as exc:
            self.__publish_event(
                VectorStoreError(
                    collection_name=collection_name,
                    operation="add_documents",
                    message=str(exc),
                )
            )
            raise

        logger.debug(f"Added {len(documents)} documents to collection {collection_name}")
        self.__publish_event(
            DocumentsAdded(
                collection_name=collection_name,
                document_count=len(documents),
            )
        )

    def search_similar(
        self,
        collection_name: str,
        query_vector: np.ndarray,
        k: int = 10,
        filter: Optional[Dict[str, Any]] = None,
        score_threshold: Optional[float] = None,
        include_vectors: bool = False,
        include_metadata: bool = True
    ) -> List[SearchResult]:
        self.initialize()

        if k <= 0:
            raise ValueError("k must be a positive integer")

        results = self.adapter.search(
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

    def get_document(
        self,
        collection_name: str,
        document_id: str,
        include_vector: bool = True
    ) -> Optional[VectorDocument]:
        self.initialize()
        return self.adapter.get_vector(
            collection_name, document_id, include_vector
        )

    def update_document(
        self,
        collection_name: str,
        document_id: str,
        vector: Optional[np.ndarray] = None,
        metadata: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None
    ) -> None:
        self.initialize()

        if vector is None and metadata is None and payload is None:
            raise ValueError("At least one of vector, metadata, or payload must be provided")

        try:
            self.adapter.update_vector(
                collection_name, document_id, vector, metadata, payload
            )
        except Exception as exc:
            self.__publish_event(
                VectorStoreError(
                    collection_name=collection_name,
                    operation="update_document",
                    message=str(exc),
                )
            )
            raise

        logger.debug(f"Updated document {document_id} in collection {collection_name}")
        self.__publish_event(
            DocumentUpdated(
                collection_name=collection_name,
                document_id=document_id,
            )
        )

    def delete_documents(
        self,
        collection_name: str,
        document_ids: List[str]
    ) -> None:
        self.initialize()

        if not document_ids:
            raise ValueError("Document IDs cannot be empty")

        try:
            self.adapter.delete_vectors(collection_name, document_ids)
        except Exception as exc:
            self.__publish_event(
                VectorStoreError(
                    collection_name=collection_name,
                    operation="delete_documents",
                    message=str(exc),
                )
            )
            raise

        logger.info(f"Deleted {len(document_ids)} documents from collection {collection_name}")
        self.__publish_event(
            DocumentsDeleted(
                collection_name=collection_name,
                document_count=len(document_ids),
            )
        )

    def get_collection_size(self, collection_name: str) -> int:
        self.initialize()
        return self.adapter.count_vectors(collection_name)

    def list_collections(self) -> List[str]:
        self.initialize()
        return self.adapter.list_collections()

    def delete_collection(self, collection_name: str) -> None:
        self.initialize()
        try:
            self.adapter.delete_collection(collection_name)
        except Exception as exc:
            self.__publish_event(
                VectorStoreError(
                    collection_name=collection_name,
                    operation="delete_collection",
                    message=str(exc),
                )
            )
            raise

        logger.info(f"Deleted collection: {collection_name}")
        self.__publish_event(CollectionDeleted(collection_name=collection_name))

    def close(self) -> None:
        if self._initialized:
            self.adapter.close()
            self._initialized = False
            logger.info("VectorStoreService closed")
