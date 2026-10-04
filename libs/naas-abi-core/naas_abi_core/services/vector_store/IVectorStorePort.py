from abc import ABC, abstractmethod
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

import numpy as np

STREAM_PAGE = 500  # documents per list_vectors call when streaming by default


@dataclass
class VectorDocument:
    id: str
    vector: np.ndarray
    metadata: dict[str, Any]
    payload: dict[str, Any] | None = None


@dataclass
class VectorPage:
    """One page of a collection's documents, in a stable adapter-defined order.

    ``next_cursor`` is opaque: pass it back as ``cursor`` to continue from the
    first document of the next page; ``None`` means this was the last page.
    """

    documents: list[VectorDocument]
    next_cursor: str | None = None


@dataclass
class CollectionInfo:
    name: str
    dimension: int | None
    distance_metric: str | None
    size: int


@dataclass
class SearchResult:
    id: str
    score: float
    vector: np.ndarray | None = None
    metadata: dict[str, Any] | None = None
    payload: dict[str, Any] | None = None


class IVectorStorePort(ABC):
    @abstractmethod
    def initialize(self) -> None:
        pass

    @abstractmethod
    def create_collection(
        self,
        collection_name: str,
        dimension: int,
        distance_metric: str = "cosine",
        **kwargs
    ) -> None:
        pass

    @abstractmethod
    def delete_collection(self, collection_name: str) -> None:
        pass

    @abstractmethod
    def list_collections(self) -> list[str]:
        pass

    @abstractmethod
    def store_vectors(
        self,
        collection_name: str,
        documents: list[VectorDocument]
    ) -> None:
        pass

    @abstractmethod
    def search(
        self,
        collection_name: str,
        query_vector: np.ndarray,
        k: int = 10,
        filter: dict[str, Any] | None = None,
        include_vectors: bool = False,
        include_metadata: bool = True
    ) -> list[SearchResult]:
        pass

    @abstractmethod
    def get_vector(
        self,
        collection_name: str,
        vector_id: str,
        include_vector: bool = True
    ) -> VectorDocument | None:
        pass

    @abstractmethod
    def update_vector(
        self,
        collection_name: str,
        vector_id: str,
        vector: np.ndarray | None = None,
        metadata: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None
    ) -> None:
        pass

    @abstractmethod
    def delete_vectors(
        self,
        collection_name: str,
        vector_ids: list[str]
    ) -> None:
        pass

    @abstractmethod
    def count_vectors(self, collection_name: str) -> int:
        pass

    @abstractmethod
    def list_vectors(
        self,
        collection_name: str,
        limit: int = 100,
        cursor: str | None = None,
        include_vectors: bool = False,
    ) -> VectorPage:
        """Page through every document, metadata and payload included.

        Without ``include_vectors`` each document's vector is an empty array.
        """

    @contextmanager
    def list_vectors_stream(
        self, collection_name: str, *, include_vectors: bool = False
    ) -> Iterator[Iterator[VectorDocument]]:
        """Every document of the collection, in ``list_vectors`` order, read
        lazily inside the block (docs/adr/20261003_nats-streamed-results.md).
        Read it once; leaving the block releases it.

        This default walks ``list_vectors`` pages of ``STREAM_PAGE`` documents,
        so memory holds one page and no lock is held between pages; adapters
        override it only when they can do better.
        """

        def documents() -> Iterator[VectorDocument]:
            cursor = None
            while True:
                page = self.list_vectors(
                    collection_name,
                    limit=STREAM_PAGE,
                    cursor=cursor,
                    include_vectors=include_vectors,
                )
                yield from page.documents
                if page.next_cursor is None:
                    return
                cursor = page.next_cursor

        yield documents()

    @abstractmethod
    def get_collection_info(self, collection_name: str) -> CollectionInfo:
        """Dimension and distance metric (``None`` when unknown) and size."""

    @abstractmethod
    def close(self) -> None:
        pass