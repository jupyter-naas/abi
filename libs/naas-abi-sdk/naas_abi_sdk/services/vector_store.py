from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from naas_abi_proto.vector_store.v1 import vector_store_pb2 as pb

from naas_abi_sdk.services._codec import ServiceProxy, decode
from naas_abi_sdk.services._streams import open_stream
from naas_abi_sdk.services.models import (
    CollectionInfo,
    SearchResult,
    VectorDocument,
    VectorPage,
)
from naas_abi_sdk.transport import RPCError

TRANSFER_PREFIX = "abi.svc.vector_store.v1.transfer"
MAX_PAGE_SIZE = 10_000  # as the engine's VectorStoreService.list_documents


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

    async def list_documents(
        self,
        collection_name: str,
        *,
        limit: int = 100,
        cursor: str | None = None,
        include_vectors: bool = False,
    ) -> VectorPage:
        """One page of a collection; follow ``next_cursor`` until it is None.
        ``list_documents_stream`` reads a whole collection."""
        if not 1 <= limit <= MAX_PAGE_SIZE:
            raise ValueError(f"limit must be between 1 and {MAX_PAGE_SIZE}")
        return await self._request(
            "list_vectors",
            collection_name=collection_name,
            limit=limit,
            cursor=cursor,
            include_vectors=include_vectors,
        )

    async def get_collection_info(self, collection_name: str) -> CollectionInfo:
        """Dimension and distance metric (None when unknown) and size."""
        return await self._request(
            "get_collection_info", collection_name=collection_name
        )

    @asynccontextmanager
    async def list_documents_stream(
        self, collection_name: str, *, include_vectors: bool = False
    ) -> AsyncIterator[AsyncIterator[VectorDocument]]:
        """Every document of a collection, fetched as it is iterated, in the
        engine's ``list_vectors`` order (docs/adr/20261003_nats-streamed-results.md).
        Read it once, inside the block; leaving closes the stream."""
        request = pb.ListVectorsRequest(
            collection_name=collection_name, include_vectors=include_vectors
        )
        async with open_stream(
            self._client, TRANSFER_PREFIX, "list_vectors", request.SerializeToString()
        ) as frames:
            if frames is None:
                raise RPCError("UNAVAILABLE", "No engine streams vector listings")
            yield _documents(frames)

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


async def _documents(frames: AsyncIterator[bytes]) -> AsyncIterator[VectorDocument]:
    async for frame in frames:
        for document in pb.VectorPage.FromString(frame).documents:
            yield decode(document)
