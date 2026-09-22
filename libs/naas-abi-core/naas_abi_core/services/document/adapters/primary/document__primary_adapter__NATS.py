"""Authenticated document RPCs; namespace scoping follows Stage 1 shared trust."""

from functools import partial

import nats.micro
from google.protobuf.message import DecodeError
from naas_abi_core import logger
from naas_abi_core.engine.nats_auth import (
    InvalidServiceTokenError,
    verify_service_token,
)
from naas_abi_core.engine.nats_dispatch import DomainRPCDispatcher
from naas_abi_core.engine.nats_rpc import respond_protobuf
from naas_abi_core.services.document.adapters.document_nats_codec import (
    ERRORS,
    decode_order,
    decode_spec,
    decode_where,
    encode_document,
)
from naas_abi_core.services.document.DocumentService import DocumentService
from naas_abi_proto.common.v1 import common_pb2
from naas_abi_proto.document.v1 import document_pb2 as pb
from naas_abi_proto.document.values import decode_data
from nats.micro.service import Service

OPERATIONS = {
    "ensure_collection": "EnsureCollection",
    "drop_collection": "DropCollection",
    "collections": "Collections",
    "put": "Put",
    "get": "Get",
    "delete": "Delete",
    "find": "Find",
    "count": "Count",
}
SUBJECT_PREFIX = "abi.svc.document.v1"


class DocumentPrimaryAdapterNATS:
    def __init__(self, service: DocumentService, jwt_secret: str) -> None:
        self._adapter = service
        self._jwt_secret = jwt_secret
        self._dispatch = DomainRPCDispatcher("document")
        self._service: Service | None = None

    async def start(self, nc: nats.NATS) -> None:
        if self._service is not None:
            return
        service = await nats.micro.add_service(nc, name="document", version="1.0.0")
        self._service = service
        for operation in OPERATIONS:
            await service.add_endpoint(
                name=operation,
                subject=f"{SUBJECT_PREFIX}.{operation}",
                handler=partial(self._handle, operation=operation),
            )

    async def stop(self) -> None:
        service, self._service = self._service, None
        try:
            if service is not None:
                await service.stop()
        finally:
            self._dispatch.close()

    async def _handle(self, request, *, operation: str) -> None:
        response_type = getattr(pb, OPERATIONS[operation] + "Response")
        try:
            verify_service_token(
                (request.headers or {}).get("Nats-Auth-Token", ""), self._jwt_secret
            )
        except InvalidServiceTokenError:
            await respond_protobuf(
                request,
                response_type(
                    error=common_pb2.CallError(
                        code="UNAUTHENTICATED", message="missing or invalid auth token"
                    )
                ),
                response_type,
            )
            return
        try:
            parsed = getattr(pb, OPERATIONS[operation] + "Request").FromString(
                request.data
            )
            result = await self._dispatch.call(partial(self._call, operation), parsed)
        except Exception as exc:  # noqa: BLE001 - translate failures at the RPC boundary
            code = next(
                (code for code, cls in ERRORS.items() if isinstance(exc, cls)),
                "INTERNAL",
            )
            if isinstance(exc, DecodeError):
                code = "INVALID_ARGUMENT"
            # Backend details may contain connection credentials or document contents.
            if code in ("INTERNAL", "STORAGE_ERROR", "ADAPTER_ERROR"):
                logger.warning(
                    f"document NATS {operation} failed: {type(exc).__name__}"
                )
            result = response_type(
                error=common_pb2.CallError(
                    code=code,
                    message=str(exc) if code == "INVALID_ARGUMENT" else code,
                    retryable=False,
                )
            )
        await respond_protobuf(request, result, response_type)

    def _call(self, operation: str, request):
        service = self._adapter._for_namespace(request.namespace)
        response = getattr(pb, OPERATIONS[operation] + "Response")
        if operation == "ensure_collection":
            service.ensure_collection(decode_spec(request.spec))
        elif operation == "drop_collection":
            service.drop_collection(request.collection)
        elif operation == "collections":
            return response(collections=service.collections())
        elif operation == "put":
            doc = service.put(
                request.collection,
                request.id,
                decode_data(request.data),
                if_version=request.if_version
                if request.HasField("if_version")
                else None,
            )
            return response(document=encode_document(doc))
        elif operation == "get":
            return response(
                document=encode_document(service.get(request.collection, request.id))
            )
        elif operation == "delete":
            service.delete(
                request.collection,
                request.id,
                if_version=request.if_version
                if request.HasField("if_version")
                else None,
            )
        elif operation == "find":
            page = service.find(
                request.collection,
                where=decode_where(request.where),
                order_by=decode_order(request),
                limit=request.limit if request.HasField("limit") else 100,
                cursor=request.cursor if request.HasField("cursor") else None,
            )
            return response(
                items=[encode_document(d) for d in page.items], cursor=page.cursor
            )
        elif operation == "count":
            return response(
                count=service.count(request.collection, decode_where(request.where))
            )
        return response()
