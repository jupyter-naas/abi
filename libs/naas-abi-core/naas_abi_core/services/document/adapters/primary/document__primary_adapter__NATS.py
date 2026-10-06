"""Authenticated document RPCs; namespace scoping follows Stage 1 shared trust.

Every authenticated caller passes its namespace explicitly. Listing namespaces
is platform administration: only ``admin_identities`` (the API and the engine
by default) may call it; anyone else gets PERMISSION_DENIED.
"""

from collections.abc import Iterable
from functools import partial

import nats.micro
from google.protobuf.message import DecodeError
from naas_abi_core import logger
from naas_abi_core.engine.nats_auth import (
    InvalidServiceTokenError,
    verify_service_token,
)
from naas_abi_core.engine.nats_dispatch import DomainRPCDispatcher
from naas_abi_core.engine.nats_rpc import (
    RequestPayloadError,
    broker_limit,
    request_payload,
    respond_protobuf,
)
from naas_abi_core.engine.nats_sessions import ServicePrimary
from naas_abi_core.engine.nats_tracing import TracedService, add_traced_service
from naas_abi_core.services.document.adapters.document_nats_codec import (
    ERRORS,
    decode_order,
    decode_spec,
    decode_where,
    encode_document,
    encode_spec,
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
    "collection_spec": "CollectionSpec",
    "put": "Put",
    "get": "Get",
    "delete": "Delete",
    "find": "Find",
    "count": "Count",
    "namespaces": "Namespaces",
}
SUBJECT_PREFIX = "abi.svc.document.v1"
# A find page's size estimate (stored JSON) stays under this share of the
# broker limit, so its reply fits without RPC overflow: protobuf can run a few
# times larger than JSON for many small values.
PAGE_SHARE = 4
# Operations across namespaces, and the service identities allowed to call them.
ADMIN_OPERATIONS = frozenset({"namespaces"})
ADMIN_IDENTITIES = frozenset({"api", "engine"})


class DocumentPrimaryAdapterNATS(ServicePrimary):
    def __init__(
        self,
        service: DocumentService,
        jwt_secret: str,
        *,
        admin_identities: Iterable[str] = ADMIN_IDENTITIES,
    ) -> None:
        self._adapter = service
        self._jwt_secret = jwt_secret
        self._admin_identities = frozenset(admin_identities)
        self._dispatch = DomainRPCDispatcher("document")
        self._service: Service | TracedService | None = None

    async def start(self, nc: nats.NATS) -> None:
        if self._service is not None:
            return
        service = await add_traced_service(nc, name="document", version="1.0.0")
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
            identity = verify_service_token(
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
        if operation in ADMIN_OPERATIONS and identity not in self._admin_identities:
            await respond_protobuf(
                request,
                response_type(
                    error=common_pb2.CallError(
                        code="PERMISSION_DENIED",
                        message=f"{operation} needs a platform service identity",
                        retryable=False,
                    )
                ),
                response_type,
            )
            return
        try:
            parsed = getattr(pb, OPERATIONS[operation] + "Request").FromString(
                await request_payload(request)
            )
            call = partial(self._call, operation)
            if operation == "find":
                limit = broker_limit(request)
                call = partial(call, page_bytes=limit // PAGE_SHARE if limit else None)
            result = await self._dispatch.call(call, parsed)
        except Exception as exc:  # noqa: BLE001 - translate failures at the RPC boundary
            code = next(
                (code for code, cls in ERRORS.items() if isinstance(exc, cls)),
                "INTERNAL",
            )
            if isinstance(exc, DecodeError):
                code = "INVALID_ARGUMENT"
            if isinstance(exc, RequestPayloadError):
                code = exc.code
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

    def _call(self, operation: str, request, page_bytes: int | None = None):
        response = getattr(pb, OPERATIONS[operation] + "Response")
        if operation == "namespaces":
            return response(namespaces=self._adapter.namespaces())
        service = self._adapter._for_namespace(request.namespace)
        if operation == "ensure_collection":
            service.ensure_collection(decode_spec(request.spec))
        elif operation == "drop_collection":
            service.drop_collection(request.collection)
        elif operation == "collections":
            return response(collections=service.collections())
        elif operation == "collection_spec":
            return response(
                spec=encode_spec(service.collection_spec(request.collection))
            )
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
                max_bytes=_smallest(
                    request.max_bytes if request.HasField("max_bytes") else None,
                    page_bytes,
                ),
            )
            return response(
                items=[encode_document(d) for d in page.items], cursor=page.cursor
            )
        elif operation == "count":
            return response(
                count=service.count(request.collection, decode_where(request.where))
            )
        return response()


def _smallest(*budgets: int | None) -> int | None:
    given = [budget for budget in budgets if budget is not None]
    return min(given) if given else None
