import logging
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import numpy as np

from naas_abi_core import logger as abi_logger
from naas_abi_core.services.iam.enforcement import ResourceGuard
from naas_abi_core.services.ServiceBase import ServiceBase
from naas_abi_core.services.vector_store.iam_catalog import (
    CATALOG,
    COLLECTION,
    SERVICE_TYPE,
    VECTOR,
)
from naas_abi_core.services.vector_store.ontologies.modules.VectorStoreEventOntology import (
    CollectionDeleted,
    CollectionEnsured,
    DocumentsAdded,
    DocumentsDeleted,
    DocumentUpdated,
    VectorStoreError,
)

from .IVectorStorePort import (
    CollectionInfo,
    CollectionNotFoundError,
    IVectorStorePort,
    SearchResult,
    VectorDocument,
    VectorPage,
)

# Bound one call: a page travels as one NATS reply in NATS mode.
MAX_PAGE_SIZE = 10_000

logger = logging.getLogger(__name__)


class VectorStoreService(ServiceBase):
    """Vector collections. Wired into an engine, every operation is authorized
    on ``collection/<name>`` or ``vector/<collection>/<id>`` (RFC §6.4): a
    collection the caller may not see is ``CollectionNotFoundError``, and
    lists hold only what the caller may list."""

    def __init__(self, adapter: IVectorStorePort):
        super().__init__()
        self.adapter = adapter
        self._initialized = False
        self._guard = ResourceGuard.of(CATALOG, self)

    def __collection(self, action: str, collection_name: str) -> None:
        self._guard.require(
            action,
            COLLECTION,
            [collection_name],
            not_found=lambda: CollectionNotFoundError(collection_name),
        )

    def __vectors(self, action: str, collection_name: str, ids: list[str]) -> None:
        """``action`` on each vector; the first denial fails the call (§6.3)."""
        self._guard.require_all(
            action,
            VECTOR,
            [[collection_name, document_id] for document_id in ids],
            not_found=lambda: CollectionNotFoundError(collection_name),
        )

    def __create(self, collection_name: str):
        return self._guard.create(
            "CreateCollection",
            COLLECTION,
            [collection_name],
            exists=lambda: collection_name in self.adapter.list_collections(),
            not_found=lambda: CollectionNotFoundError(collection_name),
        )

    def __visible(self, collection_name: str) -> None:
        self._guard.require_visible(
            COLLECTION,
            [collection_name],
            not_found=lambda: CollectionNotFoundError(collection_name),
        )

    def __listable(self, action: str, collection_name: str, documents: list) -> list:
        return self._guard.filter(
            action,
            VECTOR,
            documents,
            lambda document: [collection_name, document.id],
        )

    def __publish_event(self, event: object) -> None:
        if not self.services_wired:
            return
        if not self.services.events_available():
            return
        try:
            self.services.events.emit(event)
        except Exception as exc:  # noqa: BLE001
            # Vector store is the source of truth; event logging must never break it.
            abi_logger.warning(f"VectorStoreService: failed to publish event: {exc}")

    def initialize(self) -> None:
        """Initialize the backend: service administration (``Initialize``).

        Already initialized, it does nothing, for anyone: clients initialize
        before each call, and the owning engine initialized the store.
        """
        if self._initialized:
            return
        self._guard.require("Initialize", SERVICE_TYPE)
        self._ensure_initialized()

    def _ensure_initialized(self) -> None:
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
        **kwargs,
    ) -> None:
        self._ensure_initialized()
        commit = self.__create(collection_name)
        existing_collections = self.adapter.list_collections()
        if recreate and collection_name in existing_collections:
            # Only an actual drop needs DeleteCollection.
            self.__collection("DeleteCollection", collection_name)

        try:
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

        commit()
        self.__publish_event(CollectionEnsured(collection_name=collection_name))

    def create_collection(
        self, collection_name: str, dimension: int, distance_metric: str = "cosine"
    ) -> None:
        """Create a collection without checking for it first (the port's
        ``create_collection``); ``ensure_collection`` is the idempotent one."""
        self._ensure_initialized()
        commit = self.__create(collection_name)
        try:
            self.adapter.create_collection(collection_name, dimension, distance_metric)
        except Exception as exc:
            self.__publish_event(
                VectorStoreError(
                    collection_name=collection_name,
                    operation="ensure_collection",
                    message=str(exc),
                )
            )
            raise
        commit()
        self.__publish_event(CollectionEnsured(collection_name=collection_name))

    def add_documents(
        self,
        collection_name: str,
        ids: list[str],
        vectors: list[np.ndarray],
        metadata: list[dict[str, Any]] | None = None,
        payloads: list[dict[str, Any]] | None = None,
    ) -> None:
        self._ensure_initialized()

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
                payload=payloads[i] if payloads else None,
            )
            documents.append(doc)
        self.store_documents(collection_name, documents)

    def store_documents(
        self, collection_name: str, documents: list[VectorDocument]
    ) -> None:
        """Store documents as given (the port's ``store_vectors``)."""
        self._ensure_initialized()
        self.__vectors(
            "StoreVectors", collection_name, [document.id for document in documents]
        )
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

        logger.debug(
            f"Added {len(documents)} documents to collection {collection_name}"
        )
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
        filter: dict[str, Any] | None = None,
        score_threshold: float | None = None,
        include_vectors: bool = False,
        include_metadata: bool = True,
    ) -> list[SearchResult]:
        if k <= 0:
            raise ValueError("k must be a positive integer")

        results = self.search(
            collection_name,
            query_vector,
            k=k,
            filter=filter,
            include_vectors=include_vectors,
            include_metadata=include_metadata,
        )

        if score_threshold is not None:
            results = [r for r in results if r.score >= score_threshold]

        logger.debug(f"Found {len(results)} similar vectors in {collection_name}")
        return results

    def search(
        self,
        collection_name: str,
        query_vector: np.ndarray,
        k: int = 10,
        filter: dict[str, Any] | None = None,
        include_vectors: bool = False,
        include_metadata: bool = True,
    ) -> list[SearchResult]:
        """The port's ``search``, as given; ``search_similar`` validates first.

        Checked once, on the collection: hits are not filtered (RFC §5.5).
        """
        self._ensure_initialized()
        self.__collection("Search", collection_name)
        return self.adapter.search(
            collection_name=collection_name,
            query_vector=query_vector,
            k=k,
            filter=filter,
            include_vectors=include_vectors,
            include_metadata=include_metadata,
        )

    def get_document(
        self, collection_name: str, document_id: str, include_vector: bool = True
    ) -> VectorDocument | None:
        """The document, or None when missing or invisible to the caller."""
        self._ensure_initialized()
        try:
            self.__vectors("GetVector", collection_name, [document_id])
        except CollectionNotFoundError:
            return None
        return self.adapter.get_vector(collection_name, document_id, include_vector)

    def update_document(
        self,
        collection_name: str,
        document_id: str,
        vector: np.ndarray | None = None,
        metadata: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        if vector is None and metadata is None and payload is None:
            raise ValueError(
                "At least one of vector, metadata, or payload must be provided"
            )
        self.update_vector(collection_name, document_id, vector, metadata, payload)

    def update_vector(
        self,
        collection_name: str,
        document_id: str,
        vector: np.ndarray | None = None,
        metadata: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        """The port's ``update_vector``, as given; ``update_document`` validates first."""
        self._ensure_initialized()
        self.__vectors("UpdateVector", collection_name, [document_id])
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

    def delete_documents(self, collection_name: str, document_ids: list[str]) -> None:
        if not document_ids:
            raise ValueError("Document IDs cannot be empty")
        self.delete_vectors(collection_name, document_ids)

    def delete_vectors(self, collection_name: str, document_ids: list[str]) -> None:
        """The port's ``delete_vectors``, as given; ``delete_documents`` validates first."""
        self._ensure_initialized()
        self.__vectors("DeleteVectors", collection_name, list(document_ids))
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

        logger.info(
            f"Deleted {len(document_ids)} documents from collection {collection_name}"
        )
        self.__publish_event(
            DocumentsDeleted(
                collection_name=collection_name,
                document_count=len(document_ids),
            )
        )

    def get_collection_size(self, collection_name: str) -> int:
        self._ensure_initialized()
        self.__collection("CountVectors", collection_name)
        return self.adapter.count_vectors(collection_name)

    def list_collections(self) -> list[str]:
        """The collections the caller may list (RFC §5.5); never fails for that."""
        self._ensure_initialized()
        return self._guard.filter(
            "ListCollections",
            COLLECTION,
            self.adapter.list_collections(),
            lambda name: [name],
        )

    def list_documents(
        self,
        collection_name: str,
        *,
        limit: int = 100,
        cursor: str | None = None,
        include_vectors: bool = False,
    ) -> VectorPage:
        """Page through a collection in a stable order; pass ``next_cursor`` back."""
        if not 0 < limit <= MAX_PAGE_SIZE:
            raise ValueError(f"limit must be between 1 and {MAX_PAGE_SIZE}")
        return self.list_vectors(
            collection_name, limit=limit, cursor=cursor, include_vectors=include_vectors
        )

    def list_vectors(
        self,
        collection_name: str,
        *,
        limit: int = 100,
        cursor: str | None = None,
        include_vectors: bool = False,
    ) -> VectorPage:
        """The port's ``list_vectors``, as given; ``list_documents`` validates first.

        The collection must be visible to the caller; a page holds only the
        documents it may list, so it can be shorter than ``limit`` while
        ``next_cursor`` continues (RFC §5.5).
        """
        self._ensure_initialized()
        self.__visible(collection_name)
        everything = self._guard.allows_every("ListVectors", VECTOR)
        if not everything and self._guard.id_prefixes("ListVectors", VECTOR) == []:
            return VectorPage([], None)  # no Allow can admit a vector: no scan
        while True:
            page = self.adapter.list_vectors(
                collection_name,
                limit=limit,
                cursor=cursor,
                include_vectors=include_vectors,
            )
            if everything:
                return page
            documents = self.__listable("ListVectors", collection_name, page.documents)
            if documents or page.next_cursor is None:
                return VectorPage(documents, page.next_cursor)
            cursor = page.next_cursor

    @contextmanager
    def list_documents_stream(
        self, collection_name: str, *, include_vectors: bool = False
    ) -> Iterator[Iterator[VectorDocument]]:
        """Every document of a collection, read lazily inside the block, in
        ``list_documents`` order; for exports and whole-collection scans.

        Only the documents the caller may list, in a collection it can see.
        """
        self._ensure_initialized()
        self.__visible(collection_name)
        everything = self._guard.allows_every("ListVectorsStream", VECTOR)
        if (
            not everything
            and self._guard.id_prefixes("ListVectorsStream", VECTOR) == []
        ):
            yield iter(())  # no Allow can admit a vector: no scan
            return
        with self.adapter.list_vectors_stream(
            collection_name, include_vectors=include_vectors
        ) as documents:
            yield (
                documents if everything else self.__streamed(collection_name, documents)
            )

    def __streamed(
        self, collection_name: str, documents: Iterator[VectorDocument]
    ) -> Iterator[VectorDocument]:
        batch: list[VectorDocument] = []
        for document in documents:
            batch.append(document)
            if len(batch) == 500:
                yield from self.__listable("ListVectorsStream", collection_name, batch)
                batch = []
        yield from self.__listable("ListVectorsStream", collection_name, batch)

    def get_collection_info(self, collection_name: str) -> CollectionInfo:
        self._ensure_initialized()
        self.__collection("GetCollectionInfo", collection_name)
        return self.adapter.get_collection_info(collection_name)

    def delete_collection(self, collection_name: str) -> None:
        self._ensure_initialized()
        self.__collection("DeleteCollection", collection_name)
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
        self._guard.forget(COLLECTION, [collection_name])
        self.__publish_event(CollectionDeleted(collection_name=collection_name))

    def close(self) -> None:
        """Close the backend: service administration (``Close``)."""
        self._guard.require("Close", SERVICE_TYPE)
        if self._initialized:
            self.adapter.close()
            self._initialized = False
            logger.info("VectorStoreService closed")
