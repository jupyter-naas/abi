from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import numpy as np


@dataclass
class VectorDocument:
    id: str
    vector: np.ndarray
    metadata: Dict[str, Any]
    payload: Optional[Dict[str, Any]] = None


@dataclass
class SearchResult:
    id: str
    score: float
    vector: Optional[np.ndarray] = None
    metadata: Optional[Dict[str, Any]] = None
    payload: Optional[Dict[str, Any]] = None


class IVectorStorePort(ABC):
    @abstractmethod
    async def initialize(self) -> None:
        pass

    @abstractmethod
    async def create_collection(
        self,
        collection_name: str,
        dimension: int,
        distance_metric: str = "cosine",
        **kwargs
    ) -> None:
        pass

    @abstractmethod
    async def delete_collection(self, collection_name: str) -> None:
        pass

    @abstractmethod
    async def list_collections(self) -> List[str]:
        pass

    @abstractmethod
    async def store_vectors(
        self,
        collection_name: str,
        documents: List[VectorDocument]
    ) -> None:
        pass

    @abstractmethod
    async def search(
        self,
        collection_name: str,
        query_vector: np.ndarray,
        k: int = 10,
        filter: Optional[Dict[str, Any]] = None,
        include_vectors: bool = False,
        include_metadata: bool = True
    ) -> List[SearchResult]:
        pass

    @abstractmethod
    async def get_vector(
        self,
        collection_name: str,
        vector_id: str,
        include_vector: bool = True
    ) -> Optional[VectorDocument]:
        pass

    @abstractmethod
    async def update_vector(
        self,
        collection_name: str,
        vector_id: str,
        vector: Optional[np.ndarray] = None,
        metadata: Optional[Dict[str, Any]] = None,
        payload: Optional[Dict[str, Any]] = None
    ) -> None:
        pass

    @abstractmethod
    async def delete_vectors(
        self,
        collection_name: str,
        vector_ids: List[str]
    ) -> None:
        pass

    @abstractmethod
    async def count_vectors(self, collection_name: str) -> int:
        pass

    @abstractmethod
    async def close(self) -> None:
        pass