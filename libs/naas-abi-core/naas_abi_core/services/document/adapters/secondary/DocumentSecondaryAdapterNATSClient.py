"""Document port client with explicit namespaces and no operation replay."""

from collections.abc import Sequence

from naas_abi_core.engine.nats_rpc import NatsRPCClient
from naas_abi_core.services.document.adapters.document_nats_codec import (
    ERRORS,
    decode_document,
    encode_spec,
    encode_where,
)
from naas_abi_core.services.document.DocumentPort import (
    CollectionSpec,
    Document,
    DocumentStorageError,
    OrderBy,
    Page,
    Predicate,
    Value,
    validate_version,
)
from naas_abi_proto.document.v1 import document_pb2 as pb
from naas_abi_proto.document.values import encode_data


class DocumentSecondaryAdapterNATSClient(NatsRPCClient):
    def close(self) -> None:
        super().close()
        self._document_closed = True

    def _request(self, operation, request, response_type):
        if getattr(self, "_document_closed", False):
            raise DocumentStorageError("Document client is closed")
        request.context.CopyFrom(self._context())
        response = self._call(
            f"abi.svc.document.v1.{operation}", request, response_type
        )
        if response.HasField("error"):
            raise ERRORS.get(response.error.code, RuntimeError)(response.error.message)
        return response

    def ensure_collection(self, namespace: str, spec: CollectionSpec) -> None:
        self._request(
            "ensure_collection",
            pb.EnsureCollectionRequest(namespace=namespace, spec=encode_spec(spec)),
            pb.EnsureCollectionResponse,
        )

    def drop_collection(self, namespace: str, collection: str) -> None:
        self._request(
            "drop_collection",
            pb.DropCollectionRequest(namespace=namespace, collection=collection),
            pb.DropCollectionResponse,
        )

    def collections(self, namespace: str) -> list[str]:
        return list(
            self._request(
                "collections",
                pb.CollectionsRequest(namespace=namespace),
                pb.CollectionsResponse,
            ).collections
        )

    def put(
        self,
        namespace: str,
        collection: str,
        id: str,
        data: dict[str, Value],
        if_version: int | None,
    ) -> Document:
        validate_version(if_version)
        return decode_document(
            self._request(
                "put",
                pb.PutRequest(
                    namespace=namespace,
                    collection=collection,
                    id=id,
                    data=encode_data(data),
                    if_version=if_version,
                ),
                pb.PutResponse,
            ).document
        )

    def get(self, namespace: str, collection: str, id: str) -> Document:
        return decode_document(
            self._request(
                "get",
                pb.GetRequest(namespace=namespace, collection=collection, id=id),
                pb.GetResponse,
            ).document
        )

    def delete(
        self, namespace: str, collection: str, id: str, if_version: int | None
    ) -> None:
        validate_version(if_version)
        self._request(
            "delete",
            pb.DeleteRequest(
                namespace=namespace, collection=collection, id=id, if_version=if_version
            ),
            pb.DeleteResponse,
        )

    def find(
        self,
        namespace: str,
        collection: str,
        where: Sequence[Predicate],
        order_by: OrderBy,
        limit: int,
        cursor: str | None,
    ) -> Page:
        response = self._request(
            "find",
            pb.FindRequest(
                namespace=namespace,
                collection=collection,
                where=encode_where(where),
                order_by=pb.OrderBy(field=order_by[0], direction=order_by[1])
                if order_by
                else None,
                limit=limit,
                cursor=cursor,
            ),
            pb.FindResponse,
        )
        return Page(
            [decode_document(d) for d in response.items],
            response.cursor if response.HasField("cursor") else None,
        )

    def count(self, namespace: str, collection: str, where: Sequence[Predicate]) -> int:
        return self._request(
            "count",
            pb.CountRequest(
                namespace=namespace, collection=collection, where=encode_where(where)
            ),
            pb.CountResponse,
        ).count
