from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import numpy as np


@dataclass
class VectorDocument:
    id: str
    vector: np.ndarray
    metadata: dict[str, Any]
    payload: dict[str, Any] | None = None


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
    def close(self) -> None:
        pass