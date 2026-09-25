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

Object bytes and streams use caller-bound chunked transfers. Uploads are staged
on temporary disk before the storage operation starts.
"""

from __future__ import annotations

import io
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC
from queue import Queue
from typing import BinaryIO

from naas_abi_core import logger
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
from naas_abi_proto.transfer.v1 import transfer_pb2 as transfer_pb
from naas_abi_sdk.transfer import read_legacy_upload, transfer_subject
from nats.errors import NoRespondersError


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

    def _transfer_call(self, operation, request, response_type):
        request.context.CopyFrom(self._context())
        response = self._call(
            transfer_subject(
                f"{SUBJECT_PREFIX}.transfer", operation, getattr(request, "id", "")
            ),
            request,
            response_type,
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        return response

    def _open_transfer(self, operation, prefix, key):
        nc = self._run_coro(self._ensure_connection_async())
        size = min(64 * 1024, nc.max_payload // 2)
        return self._transfer_call(
            "open",
            transfer_pb.OpenRequest(
                operation=operation,
                metadata=object_storage_pb2.GetObjectRequest(
                    prefix=prefix, key=key
                ).SerializeToString(),
                chunk_bytes=size,
            ),
            transfer_pb.OpenResponse,
        )

    def _close_transfer(self, transfer_id: str) -> None:
        try:
            self._transfer_call(
                "close",
                transfer_pb.CloseRequest(id=transfer_id),
                transfer_pb.CloseResponse,
            )
        except Exception as exc:  # noqa: BLE001 - cleanup must preserve the operation error
            # Idle expiry cleans up when the final exchange cannot reach the owner.
            logger.warning("Transfer cleanup failed: {}", type(exc).__name__)

    def get_object(self, prefix: str, key: str) -> bytes:
        with self.get_object_stream(prefix, key) as stream:
            return stream.read()

    @contextmanager
    def get_object_stream(self, prefix: str, key: str) -> Iterator[BinaryIO]:
        try:
            opened = self._open_transfer("get", prefix, key)
        except NoRespondersError:
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
            with io.BytesIO(response.content) as stream:
                yield stream
            return
        try:
            self._transfer_call(
                "start",
                transfer_pb.StartRequest(id=opened.id),
                transfer_pb.StartResponse,
            )
            with io.BufferedReader(_RemoteReader(self, opened.id)) as stream:
                stream.peek(
                    1
                )  # Surface open/read errors before entering the caller body.
                yield stream
        finally:
            self._close_transfer(opened.id)

    def put_object(self, prefix: str, key: str, content: bytes) -> None:
        nc = self._run_coro(self._ensure_connection_async())
        if len(content) <= min(64 * 1024, nc.max_payload // 2):
            self._put_unary(prefix, key, content)
        else:
            self.put_object_stream(prefix, key, io.BytesIO(content))

    def _put_unary(self, prefix, key, content):
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
        try:
            opened = self._open_transfer("put", prefix, key)
        except NoRespondersError:
            nc = self._run_coro(self._ensure_connection_async())
            limit = min(nc.max_payload, 8 * 1024 * 1024)
            content = read_legacy_upload(stream, limit)
            self._put_unary(prefix, key, content)
            return
        try:
            sequence = 0
            while chunk := stream.read(opened.chunk_bytes):
                self._transfer_call(
                    "write",
                    transfer_pb.WriteRequest(
                        id=opened.id, sequence=sequence, data=chunk
                    ),
                    transfer_pb.WriteResponse,
                )
                sequence += 1
            self._transfer_call(
                "start",
                transfer_pb.StartRequest(id=opened.id),
                transfer_pb.StartResponse,
            )
            reader = _RemoteReader(self, opened.id)
            reader.read()
        finally:
            self._close_transfer(opened.id)

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


class _RemoteReader(io.RawIOBase):
    def __init__(self, client, id):
        super().__init__()
        self.client, self.id = client, id
        self.sequence = 0
        self.buffer = bytearray()
        self.done = False

    def readable(self):
        return True

    def readinto(self, target):
        if self.closed:
            raise ValueError("Stream is closed")
        while not self.buffer and not self.done:
            response = self.client._transfer_call(
                "read",
                transfer_pb.ReadRequest(id=self.id, sequence=self.sequence),
                transfer_pb.ReadResponse,
            )
            if response.sequence != self.sequence:
                raise ValueError("Transfer sequence mismatch")
            if response.done:
                self.done = True
            elif response.pending:
                time.sleep(0.02)
            else:
                self.sequence += 1
                self.buffer.extend(response.data)
        count = min(len(target), len(self.buffer))
        target[:count] = self.buffer[:count]
        del self.buffer[:count]
        return count
