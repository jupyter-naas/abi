from __future__ import annotations

from collections.abc import AsyncIterator, Iterable, Mapping
from datetime import datetime
from typing import Any

from naas_abi_proto.document.v1 import document_pb2 as pb
from naas_abi_proto.document.values import decode_data, encode_data, encode_value

from naas_abi_sdk.services._codec import ServiceProxy, message
from naas_abi_sdk.services.errors import DocumentNotFound, domain_error
from naas_abi_sdk.services.models import CollectionSpec, Document, Page
from naas_abi_sdk.transport import RPCError

Predicate = tuple[str, str, Any]
OrderBy = tuple[str, str] | None


def _document(doc) -> Document:
    return Document(
        doc.id,
        decode_data(doc.data),
        datetime.fromisoformat(doc.created_at),
        datetime.fromisoformat(doc.updated_at),
        doc.version,
    )


def _where(where):
    return [
        pb.Predicate(field=f, operator=o, value=encode_value(v)) for f, o, v in where
    ]


class DocumentService(ServiceProxy):
    domain = "document"

    @property
    def namespace(self) -> str:
        return self._client.namespace

    @property
    def rpc(self):
        """Explicit low-level escape hatch, retaining this module's namespace."""
        return self._client

    async def _call(self, operation, request):
        try:
            return await getattr(self._client, operation)(request)
        except RPCError as exc:
            raise domain_error(exc) from exc

    async def ensure_collection(self, spec: CollectionSpec) -> None:
        await self._call(
            "ensure_collection",
            pb.EnsureCollectionRequest(
                spec=pb.CollectionSpec(
                    name=spec.name,
                    fields=[message(pb.FieldSpec, f) for f in spec.fields],
                    unique_together=[
                        pb.UniqueGroup(fields=g) for g in spec.unique_together
                    ],
                )
            ),
        )

    async def drop_collection(self, collection: str) -> None:
        await self._call(
            "drop_collection", pb.DropCollectionRequest(collection=collection)
        )

    async def collections(self) -> list[str]:
        return list(
            (await self._call("collections", pb.CollectionsRequest())).collections
        )

    async def put(
        self,
        collection: str,
        id: str,
        data: dict[str, Any],
        *,
        if_version: int | None = None,
    ) -> Document:
        result = await self._call(
            "put",
            pb.PutRequest(
                collection=collection,
                id=id,
                data=encode_data(data),
                if_version=if_version,
            ),
        )
        return _document(result.document)

    async def get(self, collection: str, id: str) -> Document:
        return _document(
            (
                await self._call("get", pb.GetRequest(collection=collection, id=id))
            ).document
        )

    async def exists(self, collection: str, id: str) -> bool:
        try:
            await self.get(collection, id)
        except DocumentNotFound:
            return False
        return True

    async def delete(
        self, collection: str, id: str, *, if_version: int | None = None
    ) -> None:
        await self._call(
            "delete",
            pb.DeleteRequest(collection=collection, id=id, if_version=if_version),
        )

    async def find(
        self,
        collection: str,
        *,
        where: Iterable[Predicate] = (),
        order_by: OrderBy = None,
        limit: int = 100,
        cursor: str | None = None,
    ) -> Page:
        if type(limit) is not int or not 1 <= limit <= 1000:
            raise ValueError("Page size must be between 1 and 1000")
        result = await self._call(
            "find",
            pb.FindRequest(
                collection=collection,
                where=_where(where),
                order_by=pb.OrderBy(field=order_by[0], direction=order_by[1])
                if order_by
                else None,
                limit=limit,
                cursor=cursor,
            ),
        )
        return Page(
            [_document(d) for d in result.items],
            result.cursor if result.HasField("cursor") else None,
        )

    async def iterate(
        self,
        collection: str,
        *,
        where: Iterable[Predicate] = (),
        order_by: OrderBy = None,
        batch: int = 500,
    ) -> AsyncIterator[Document]:
        predicates = tuple(where)
        cursor = None
        while True:
            page = await self.find(
                collection,
                where=predicates,
                order_by=order_by,
                limit=batch,
                cursor=cursor,
            )
            for doc in page.items:
                yield doc
            if page.cursor is None:
                break
            cursor = page.cursor

    async def find_one(
        self, collection: str, where: Iterable[Predicate]
    ) -> Document | None:
        page = await self.find(collection, where=where, limit=1)
        return page.items[0] if page.items else None

    async def count(self, collection: str, where: Iterable[Predicate] = ()) -> int:
        return (
            await self._call(
                "count", pb.CountRequest(collection=collection, where=_where(where))
            )
        ).count

    async def put_many(
        self, collection: str, items: Mapping[str, dict[str, Any]]
    ) -> list[Document]:
        return [await self.put(collection, id, data) for id, data in items.items()]

    async def delete_many(self, collection: str, where: Iterable[Predicate]) -> int:
        count = 0
        async for doc in self.iterate(collection, where=where):
            await self.delete(collection, doc.id, if_version=doc.version)
            count += 1
        return count
