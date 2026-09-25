"""NATS RPC primary adapter for the object_storage kernel domain.

Exposes a real ``IObjectStorageAdapter`` as a NATS micro-service (see
``naas_abi_core/proto/object_storage/v1/object_storage.proto`` for the wire
contract and ``naas_abi_core/proto/README.md`` for why it lives there). This
is the server side; the matching client is
``ObjectStorageSecondaryAdapterNATSClient``.

Stage 1 auth model (see ``naas_abi_core.engine.nats_auth``): one shared
secret, one claim -- which known first-party process holds the token. Every
incoming request must carry a valid token in the ``Nats-Auth-Token`` header
(``AUTH_HEADER``, imported from ``object_storage_nats_contract`` below --
that's a neutral module neither adapter owns, so this file and the client's
don't depend on each other; see that module's docstring for why).

Streaming uses the shared transfer/v1 contract under this domain's subjects.
The unary v1 endpoints remain available for existing clients.
"""

from __future__ import annotations

import io
from collections.abc import Callable
from typing import TypeVar

import nats
import nats.micro
from google.protobuf.message import DecodeError, Message
from naas_abi_core import logger
from naas_abi_core.engine.nats_auth import (
    InvalidServiceTokenError,
    verify_service_token,
)
from naas_abi_core.engine.nats_dispatch import DomainRPCDispatcher
from naas_abi_core.engine.nats_rpc import respond_protobuf
from naas_abi_core.engine.nats_transfer import TransferHost, stream_thread
from naas_abi_core.proto.common.v1 import common_pb2
from naas_abi_core.proto.object_storage.v1 import object_storage_pb2
from naas_abi_core.services.object_storage.adapters.object_storage_nats_contract import (
    AUTH_HEADER,
    SERVICE_NAME,
    SERVICE_VERSION,
    SUBJECT_PREFIX,
)
from naas_abi_core.services.object_storage.ObjectStoragePort import (
    Exceptions,
    IObjectStorageAdapter,
    IObjectStorageDomain,
    ObjectMetaData,
)
from nats.micro.request import Request
from nats.micro.service import Service

__all__ = [
    "AUTH_HEADER",
    "SERVICE_NAME",
    "SERVICE_VERSION",
    "SUBJECT_PREFIX",
    "ObjectStoragePrimaryAdapterNATS",
]

_RequestT = TypeVar("_RequestT", bound=Message)
_ResponseT = TypeVar("_ResponseT", bound=Message)


def _metadata_to_pb(metadata: ObjectMetaData) -> object_storage_pb2.ObjectMetaData:
    """Convert the port's ``ObjectMetaData`` into its wire shape.

    The optional fields (timestamps, permissions, mime_type, encoding) are
    left unset rather than sent as empty strings when the adapter didn't
    populate them, so ``HasField`` on the client side reflects "the adapter
    didn't know this" rather than "this really is empty".
    """
    pb = object_storage_pb2.ObjectMetaData(
        file_path=metadata.file_path,
        file_name=metadata.file_name,
        file_size_bytes=metadata.file_size_bytes,
    )
    if metadata.created_time is not None:
        pb.created_time.FromDatetime(metadata.created_time)
    if metadata.modified_time is not None:
        pb.modified_time.FromDatetime(metadata.modified_time)
    if metadata.accessed_time is not None:
        pb.accessed_time.FromDatetime(metadata.accessed_time)
    if metadata.permissions is not None:
        pb.permissions = metadata.permissions
    if metadata.mime_type is not None:
        pb.mime_type = metadata.mime_type
    if metadata.encoding is not None:
        pb.encoding = metadata.encoding
    return pb


class ObjectStoragePrimaryAdapterNATS:
    """Serves object storage over NATS RPC (request/reply).

    Wraps a real adapter *or* the domain service and registers one NATS
    micro-service endpoint per non-streaming method. Each endpoint
    authenticates the caller via ``Nats-Auth-Token`` before doing anything
    else, then decodes the Protobuf request, calls straight through to the
    wrapped object, and encodes a Protobuf response. Errors -- auth
    failures, known domain exceptions, anything unexpected -- are always
    reported as a normal response carrying a populated ``CallError``, never
    as a crashed handler or a raw NATS-level error.

    Accepts either an ``IObjectStorageAdapter`` (a bare secondary adapter,
    e.g. in tests) or an ``ObjectStorageService``/``IObjectStorageDomain``
    (the real engine-loaded domain service) -- deliberately, not for
    convenience: wrapping the raw adapter instead of the domain service
    would silently skip ``ObjectStorageService``'s event publishing
    (``ObjectPut``/``ObjectDeleted``) and prefix normalization for every
    remote caller, which would only diverge from in-process behaviour, not
    match it. ``EngineNATSLoader`` always passes the domain service.
    """

    def __init__(
        self,
        adapter: IObjectStorageAdapter | IObjectStorageDomain,
        jwt_secret: str,
        *,
        transfer_options: dict | None = None,
    ) -> None:
        self._adapter = adapter
        self._jwt_secret = jwt_secret
        self._dispatch = DomainRPCDispatcher(SERVICE_NAME)
        self._transfer = TransferHost(
            f"{SUBJECT_PREFIX}.transfer",
            jwt_secret,
            self._transfer_frames,
            operations=("get", "put"),
            error_mapper=self._transfer_error,
            **(transfer_options or {}),
        )
        self._service: Service | None = None

    async def start(self, nc: nats.NATS) -> None:
        """Register the ``object_storage`` NATS service on ``nc``.

        ``nc`` must already be connected -- this adapter never manages the
        connection lifecycle itself, only the service/endpoints layered on
        top of it. Calling this more than once is a no-op.
        """
        if self._service is not None:
            return

        service = await nats.micro.add_service(
            nc,
            name=SERVICE_NAME,
            version=SERVICE_VERSION,
            description="ABI kernel object_storage domain, exposed over NATS RPC (v1).",
        )
        await service.add_endpoint(
            name="get_object",
            subject=f"{SUBJECT_PREFIX}.get_object",
            handler=self._handle_get_object,
        )
        await service.add_endpoint(
            name="put_object",
            subject=f"{SUBJECT_PREFIX}.put_object",
            handler=self._handle_put_object,
        )
        await service.add_endpoint(
            name="delete_object",
            subject=f"{SUBJECT_PREFIX}.delete_object",
            handler=self._handle_delete_object,
        )
        await service.add_endpoint(
            name="list_objects",
            subject=f"{SUBJECT_PREFIX}.list_objects",
            handler=self._handle_list_objects,
        )
        await service.add_endpoint(
            name="list_objects_recursive",
            subject=f"{SUBJECT_PREFIX}.list_objects_recursive",
            handler=self._handle_list_objects_recursive,
        )
        await service.add_endpoint(
            name="get_object_metadata",
            subject=f"{SUBJECT_PREFIX}.get_object_metadata",
            handler=self._handle_get_object_metadata,
        )
        self._service = service
        await self._transfer.start(nc)

    async def stop(self) -> None:
        """Deregister the service, draining its subscriptions."""
        await self._transfer.stop()
        service = self._service
        self._service = None
        try:
            if service is not None:
                await service.stop()
        finally:
            self._dispatch.close()

    @staticmethod
    def _transfer_error(exc):
        if isinstance(exc, Exceptions.ObjectNotFound):
            return "OBJECT_NOT_FOUND", "Object not found"
        if isinstance(exc, Exceptions.ObjectAlreadyExists):
            return "OBJECT_ALREADY_EXISTS", "Object already exists"
        return None

    async def _transfer_frames(self, operation, metadata, source):
        request = object_storage_pb2.GetObjectRequest.FromString(metadata)
        if operation == "put":
            await stream_thread(
                self._adapter.put_object_stream,
                request.prefix,
                request.key,
                source if source is not None else io.BytesIO(),
            )
            return
        context = self._adapter.get_object_stream(request.prefix, request.key)
        opened = []

        def enter():
            stream = context.__enter__()
            opened.append(stream)
            return stream

        try:
            stream = await stream_thread(enter)
            while data := await stream_thread(stream.read, self._transfer.chunk_bytes):
                yield data
        finally:
            if opened:
                await stream_thread(context.__exit__, None, None, None)

    # ------------------------------------------------------------------
    # Shared request handling: auth, decode, dispatch, encode.
    # ------------------------------------------------------------------

    async def _handle(
        self,
        request: Request,
        request_cls: type[_RequestT],
        response_cls: Callable[..., _ResponseT],
        call: Callable[[_RequestT], _ResponseT],
    ) -> None:
        if not self._is_authenticated(request):
            await self._respond_error(
                request,
                response_cls,
                "UNAUTHENTICATED",
                "missing or invalid auth token",
                retryable=False,
            )
            return

        parsed_request = request_cls()
        try:
            parsed_request.ParseFromString(request.data)
        except DecodeError:
            await self._respond_error(
                request,
                response_cls,
                "INVALID_ARGUMENT",
                "invalid protobuf request",
                retryable=False,
            )
            return

        try:
            # The adapter port is synchronous and may block for seconds (network
            # round trips, slow backends). Every primary shares ONE event loop and
            # ONE connection (nats_runtime), so run the call on a worker thread:
            # inline it would stall every other endpoint of every service in the
            # process, plus nats-py's own PING/PONG handling.
            response = await self._dispatch.call(call, parsed_request)
        except Exceptions.ObjectNotFound as exc:
            await self._respond_error(
                request, response_cls, "OBJECT_NOT_FOUND", str(exc), retryable=False
            )
            return
        except Exceptions.ObjectAlreadyExists as exc:
            await self._respond_error(
                request,
                response_cls,
                "OBJECT_ALREADY_EXISTS",
                str(exc),
                retryable=False,
            )
            return
        except Exception:  # noqa: BLE001 - a handler must never crash the service
            logger.opt(exception=True).error(
                f"ObjectStoragePrimaryAdapterNATS: unexpected error handling {request.subject!r}"
            )
            await self._respond_error(
                request, response_cls, "INTERNAL", "internal error", retryable=True
            )
            return

        await respond_protobuf(request, response, response_cls)

    def _is_authenticated(self, request: Request) -> bool:
        headers = request.headers or {}
        token = headers.get(AUTH_HEADER)
        if not token:
            return False
        try:
            verify_service_token(token, self._jwt_secret)
        except InvalidServiceTokenError:
            return False
        return True

    @staticmethod
    async def _respond_error(
        request: Request,
        response_cls: Callable[..., Message],
        code: str,
        message: str,
        *,
        retryable: bool,
    ) -> None:
        response = response_cls(
            error=common_pb2.CallError(code=code, message=message, retryable=retryable)
        )
        await respond_protobuf(request, response, response_cls)

    # ------------------------------------------------------------------
    # Endpoint handlers -- one per non-streaming IObjectStorageAdapter method.
    # ------------------------------------------------------------------

    async def _handle_get_object(self, request: Request) -> None:
        await self._handle(
            request,
            object_storage_pb2.GetObjectRequest,
            object_storage_pb2.GetObjectResponse,
            self._call_get_object,
        )

    def _call_get_object(
        self, req: object_storage_pb2.GetObjectRequest
    ) -> object_storage_pb2.GetObjectResponse:
        content = self._adapter.get_object(req.prefix, req.key)
        return object_storage_pb2.GetObjectResponse(content=content)

    async def _handle_put_object(self, request: Request) -> None:
        await self._handle(
            request,
            object_storage_pb2.PutObjectRequest,
            object_storage_pb2.PutObjectResponse,
            self._call_put_object,
        )

    def _call_put_object(
        self, req: object_storage_pb2.PutObjectRequest
    ) -> object_storage_pb2.PutObjectResponse:
        limit = self._transfer.max_upload_bytes
        if limit is not None and len(req.content) > limit:
            return object_storage_pb2.PutObjectResponse(
                error=common_pb2.CallError(
                    code="PAYLOAD_TOO_LARGE",
                    message="Configured total upload limit exceeded",
                )
            )
        self._adapter.put_object(req.prefix, req.key, req.content)
        return object_storage_pb2.PutObjectResponse()

    async def _handle_delete_object(self, request: Request) -> None:
        await self._handle(
            request,
            object_storage_pb2.DeleteObjectRequest,
            object_storage_pb2.DeleteObjectResponse,
            self._call_delete_object,
        )

    def _call_delete_object(
        self, req: object_storage_pb2.DeleteObjectRequest
    ) -> object_storage_pb2.DeleteObjectResponse:
        self._adapter.delete_object(req.prefix, req.key)
        return object_storage_pb2.DeleteObjectResponse()

    async def _handle_list_objects(self, request: Request) -> None:
        await self._handle(
            request,
            object_storage_pb2.ListObjectsRequest,
            object_storage_pb2.ListObjectsResponse,
            self._call_list_objects,
        )

    def _call_list_objects(
        self, req: object_storage_pb2.ListObjectsRequest
    ) -> object_storage_pb2.ListObjectsResponse:
        keys = self._adapter.list_objects(req.prefix)
        return object_storage_pb2.ListObjectsResponse(
            keys=object_storage_pb2.Keys(keys=keys)
        )

    async def _handle_list_objects_recursive(self, request: Request) -> None:
        await self._handle(
            request,
            object_storage_pb2.ListObjectsRecursiveRequest,
            object_storage_pb2.ListObjectsRecursiveResponse,
            self._call_list_objects_recursive,
        )

    def _call_list_objects_recursive(
        self, req: object_storage_pb2.ListObjectsRecursiveRequest
    ) -> object_storage_pb2.ListObjectsRecursiveResponse:
        keys = self._adapter.list_objects_recursive(req.prefix)
        return object_storage_pb2.ListObjectsRecursiveResponse(
            keys=object_storage_pb2.Keys(keys=keys)
        )

    async def _handle_get_object_metadata(self, request: Request) -> None:
        await self._handle(
            request,
            object_storage_pb2.GetObjectMetadataRequest,
            object_storage_pb2.GetObjectMetadataResponse,
            self._call_get_object_metadata,
        )

    def _call_get_object_metadata(
        self, req: object_storage_pb2.GetObjectMetadataRequest
    ) -> object_storage_pb2.GetObjectMetadataResponse:
        metadata = self._adapter.get_object_metadata(req.prefix, req.key)
        return object_storage_pb2.GetObjectMetadataResponse(
            metadata=_metadata_to_pb(metadata)
        )
