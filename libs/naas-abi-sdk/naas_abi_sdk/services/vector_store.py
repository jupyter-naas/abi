from __future__ import annotations

from typing import Any

from naas_abi_sdk.services._codec import ServiceProxy
from naas_abi_sdk.services.models import SearchResult, VectorDocument


class VectorStoreService(ServiceProxy):
    domain = "vector_store"

    async def initialize(self) -> None:
        await self._request("initialize")

    async def ensure_collection(
        self,
        collection_name: str,
        dimension: int,
        distance_metric: str = "cosine",
        recreate: bool = False,
        **kwargs,
    ) -> None:
        if kwargs:
            raise NotImplementedError(
                "Backend-specific collection options have no remote contract"
            )
        await self.initialize()
        if collection_name in await self.list_collections():
            if not recreate:
                return
            await self.delete_collection(collection_name)
        await self._request(
            "create_collection",
            collection_name=collection_name,
            dimension=dimension,
            distance_metric=distance_metric,
        )

    async def add_documents(
        self,
        collection_name: str,
        ids: list[str],
        vectors,
        metadata: list[dict[str, Any]] | None = None,
        payloads: list[dict[str, Any]] | None = None,
    ) -> None:
        if not ids or len(ids) != len(vectors):
            raise ValueError("IDs and vectors must have matching nonzero lengths")
        if metadata is not None and len(metadata) != len(ids):
            raise ValueError("Metadata must match IDs")
        if payloads is not None and len(payloads) != len(ids):
            raise ValueError("Payloads must match IDs")
        await self.initialize()
        await self._request(
            "store_vectors",
            collection_name=collection_name,
            documents=[
                {
                    "id": id,
                    "vector": v,
                    "metadata": metadata[i] if metadata else {},
                    "payload": payloads[i] if payloads else None,
                }
                for i, (id, v) in enumerate(zip(ids, vectors))
            ],
        )

    async def search_similar(
        self,
        collection_name: str,
        query_vector,
        k: int = 10,
        filter: dict[str, Any] | None = None,
        score_threshold: float | None = None,
        include_vectors: bool = False,
        include_metadata: bool = True,
    ) -> list[SearchResult]:
        results = await self._request(
            "search",
            collection_name=collection_name,
            query_vector=[float(v) for v in query_vector],
            k=k,
            filter=filter,
            include_vectors=include_vectors,
            include_metadata=include_metadata,
        )
        return [
            r for r in results if score_threshold is None or r.score >= score_threshold
        ]

    async def get_document(
        self, collection_name: str, document_id: str, include_vector: bool = True
    ) -> VectorDocument | None:
        return await self._request(
            "get_vector",
            collection_name=collection_name,
            vector_id=document_id,
            include_vector=include_vector,
        )

    async def update_document(
        self,
        collection_name: str,
        document_id: str,
        vector=None,
        metadata: dict[str, Any] | None = None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        await self._request(
            "update_vector",
            collection_name=collection_name,
            vector_id=document_id,
            vector=vector,
            metadata=metadata,
            payload=payload,
        )

    async def delete_documents(
        self, collection_name: str, document_ids: list[str]
    ) -> None:
        await self._request(
            "delete_vectors", collection_name=collection_name, vector_ids=document_ids
        )

    async def get_collection_size(self, collection_name: str) -> int:
        return await self._request("count_vectors", collection_name=collection_name)

    async def list_collections(self) -> list[str]:
        return await self._request("list_collections")

    async def delete_collection(self, collection_name: str) -> None:
        await self._request("delete_collection", collection_name=collection_name)

    async def close(self) -> None:
        raise NotImplementedError(
            "Remote administrative shutdown is available only through engine.rpc.vector_store.close"
        )
