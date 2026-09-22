"""NATS RPC client adapter for the object_storage kernel domain.

Implements ``IObjectStorageAdapter`` by calling out to a remote
``ObjectStoragePrimaryAdapterNATS`` over NATS request/reply -- see
``naas_abi_core/proto/object_storage/v1/object_storage.proto`` for the wire
contract and ``naas_abi_core/proto/README.md`` for why it lives there.

Shared connection, token, timeout, and reply handling live in
``naas_abi_core.engine.nats_rpc.NatsRPCClient``. Calls are never replayed
by the transport after failure; a timeout may hide a completed operation.

Stage 1 auth model (see ``naas_abi_core.engine.nats_auth``): a JWT asserting
``service_identity`` is issued once and attached on the ``Nats-Auth-Token``
header of every request, reissued only when it is close to expiry rather
than on every call. ``ObjectStoragePrimaryAdapterNATS`` must read the token
from that exact header -- both sides read ``AUTH_HEADER`` from
``object_storage_nats_contract``, a neutral module neither adapter owns, so
this file never has to import from the primary adapter's module (or vice
versa) just to agree on a header name.

``get_object_stream``/``put_object_stream`` are explicitly out of scope for
this v1 contract (see the ``.proto`` file's header comment): there is no
NATS subject for either, so both raise ``NotImplementedError`` here rather
than silently buffering a stream into memory.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC
from queue import Queue
from typing import BinaryIO

from naas_abi_core.engine.nats_rpc import NatsRPCClient
from naas_abi_core.proto.common.v1 import common_pb2
from naas_abi_core.proto.object_storage.v1 import object_storage_pb2
from naas_abi_core.services.object_storage.adapters.object_storage_nats_contract import (
    AUTH_HEADER,
    SUBJECT_PREFIX,
)
from naas_abi_core.services.object_storage.ObjectStoragePort import (
    Exceptions,
    IObjectStorageAdapter,
    ObjectMetaData,
)


def _pb_to_metadata(pb: object_storage_pb2.ObjectMetaData) -> ObjectMetaData:
    return ObjectMetaData(
        file_path=pb.file_path,
        file_name=pb.file_name,
        file_size_bytes=pb.file_size_bytes,
        created_time=pb.created_time.ToDatetime(tzinfo=UTC)
        if pb.HasField("created_time")
        else None,
        modified_time=pb.modified_time.ToDatetime(tzinfo=UTC)
        if pb.HasField("modified_time")
        else None,
        accessed_time=pb.accessed_time.ToDatetime(tzinfo=UTC)
        if pb.HasField("accessed_time")
        else None,
        permissions=pb.permissions if pb.HasField("permissions") else None,
        mime_type=pb.mime_type if pb.HasField("mime_type") else None,
        encoding=pb.encoding if pb.HasField("encoding") else None,
    )


def _raise_for_error(error: common_pb2.CallError) -> None:
    """Raise the exception matching ``error.code``.

    Must stay exactly symmetric with how ``ObjectStoragePrimaryAdapterNATS``
    encodes errors -- the generic adapter contract test asserts on the real
    exception types, not on the wire code.
    """
    if error.code == "OBJECT_NOT_FOUND":
        raise Exceptions.ObjectNotFound(error.message)
    if error.code == "OBJECT_ALREADY_EXISTS":
        raise Exceptions.ObjectAlreadyExists(error.message)
    raise RuntimeError(
        f"object_storage NATS RPC failed ({error.code}): {error.message}"
    )


class ObjectStorageSecondaryAdapterNATSClient(NatsRPCClient, IObjectStorageAdapter):
    """Calls a remote ``ObjectStoragePrimaryAdapterNATS`` over NATS RPC."""

    def __init__(
        self,
        nats_url: str,
        jwt_secret: str,
        service_identity: str,
        timeout_seconds: float = 10.0,
    ) -> None:
        super().__init__(
            nats_url,
            jwt_secret,
            service_identity,
            timeout_seconds,
            auth_header=AUTH_HEADER,
        )

    # ------------------------------------------------------------------
    # IObjectStorageAdapter.
    # ------------------------------------------------------------------

    def get_object(self, prefix: str, key: str) -> bytes:
        request = object_storage_pb2.GetObjectRequest(
            context=self._context(), prefix=prefix, key=key
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.get_object",
            request,
            object_storage_pb2.GetObjectResponse,
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        return response.content

    @contextmanager
    def get_object_stream(self, prefix: str, key: str) -> Iterator[BinaryIO]:
        raise NotImplementedError(
            "ObjectStorageSecondaryAdapterNATSClient does not support streaming reads: "
            "get_object_stream is out of scope for the v1 object_storage NATS RPC contract."
        )
        yield  # pragma: no cover - unreachable, keeps this a generator matching the port

    def put_object(self, prefix: str, key: str, content: bytes) -> None:
        request = object_storage_pb2.PutObjectRequest(
            context=self._context(), prefix=prefix, key=key, content=content
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.put_object",
            request,
            object_storage_pb2.PutObjectResponse,
        )
        if response.HasField("error"):
            _raise_for_error(response.error)

    def put_object_stream(self, prefix: str, key: str, stream: BinaryIO) -> None:
        raise NotImplementedError(
            "ObjectStorageSecondaryAdapterNATSClient does not support streaming writes: "
            "put_object_stream is out of scope for the v1 object_storage NATS RPC contract."
        )

    def delete_object(self, prefix: str, key: str) -> None:
        request = object_storage_pb2.DeleteObjectRequest(
            context=self._context(), prefix=prefix, key=key
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.delete_object",
            request,
            object_storage_pb2.DeleteObjectResponse,
        )
        if response.HasField("error"):
            _raise_for_error(response.error)

    def list_objects(self, prefix: str, queue: Queue | None = None) -> list[str]:
        request = object_storage_pb2.ListObjectsRequest(
            context=self._context(), prefix=prefix
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.list_objects",
            request,
            object_storage_pb2.ListObjectsResponse,
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        keys = list(response.keys.keys)
        if queue is not None:
            for key in keys:
                queue.put(key)
        return keys

    def list_objects_recursive(
        self, prefix: str, queue: Queue | None = None
    ) -> list[str]:
        request = object_storage_pb2.ListObjectsRecursiveRequest(
            context=self._context(), prefix=prefix
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.list_objects_recursive",
            request,
            object_storage_pb2.ListObjectsRecursiveResponse,
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        keys = list(response.keys.keys)
        if queue is not None:
            for key in keys:
                queue.put(key)
        return keys

    def get_object_metadata(self, prefix: str, key: str) -> ObjectMetaData:
        request = object_storage_pb2.GetObjectMetadataRequest(
            context=self._context(), prefix=prefix, key=key
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.get_object_metadata",
            request,
            object_storage_pb2.GetObjectMetadataResponse,
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        return _pb_to_metadata(response.metadata)
