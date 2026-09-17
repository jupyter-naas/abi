"""NATS RPC client adapter for the object_storage kernel domain.

Implements ``IObjectStorageAdapter`` by calling out to a remote
``ObjectStoragePrimaryAdapterNATS`` over NATS request/reply -- see
``naas_abi_core/proto/object_storage/v1/object_storage.proto`` for the wire
contract and ``naas_abi_core/proto/README.md`` for why it lives there.

``nats-py`` has no synchronous client, so -- like
``naas_abi_core.services.bus.adapters.secondary.NATSJetStreamAdapter`` -- this
adapter bridges async NATS onto the synchronous port with ONE persistent
background thread running its own asyncio event loop (started lazily on
first use) and a single NATS connection reused across calls. Every
synchronous port method submits its async request via
``asyncio.run_coroutine_threadsafe(coro, loop).result(timeout=...)`` and
blocks until it completes or raises, retrying once on a stale connection --
same shape as ``NATSJetStreamAdapter.publish``.

Stage 1 auth model (see ``naas_abi_core.engine.nats_auth``): a JWT asserting
``service_identity`` is issued once and attached on the ``Nats-Auth-Token``
header of every request, reissued only when it is close to expiry rather
than on every call. ``ObjectStoragePrimaryAdapterNATS`` must read the token
from that exact header -- both sides of this contract must agree on the
name.

``get_object_stream``/``put_object_stream`` are explicitly out of scope for
this v1 contract (see the ``.proto`` file's header comment): there is no
NATS subject for either, so both raise ``NotImplementedError`` here rather
than silently buffering a stream into memory.
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from queue import Queue
from threading import Event as ThreadingEvent
from threading import RLock, Thread
from typing import BinaryIO, Self, TypeVar

import nats
from google.protobuf.message import Message
from naas_abi_core import logger
from naas_abi_core.engine.nats_auth import DEFAULT_TTL, issue_service_token
from naas_abi_core.proto.common.v1 import common_pb2
from naas_abi_core.proto.object_storage.v1 import object_storage_pb2
from naas_abi_core.services.object_storage.adapters.primary.object_storage__primary_adapter__NATS import (
    AUTH_HEADER,
    SUBJECT_PREFIX,
)
from naas_abi_core.services.object_storage.ObjectStoragePort import (
    Exceptions,
    IObjectStorageAdapter,
    ObjectMetaData,
)
from nats.aio.client import Client as NATSClient

_DEFAULT_TIMEOUT_SECONDS = 10.0
# Reissue the token this long before it actually expires, so a call that's
# in flight while the token is borderline doesn't get rejected mid-request.
_TOKEN_RENEWAL_MARGIN = timedelta(minutes=5)

_ResponseT = TypeVar("_ResponseT", bound=Message)


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
    raise RuntimeError(f"object_storage NATS RPC failed ({error.code}): {error.message}")


class ObjectStorageSecondaryAdapterNATSClient(IObjectStorageAdapter):
    """Calls a remote ``ObjectStoragePrimaryAdapterNATS`` over NATS RPC."""

    def __init__(
        self,
        nats_url: str,
        jwt_secret: str,
        service_identity: str,
        timeout_seconds: float = _DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self._nats_url = nats_url
        self._jwt_secret = jwt_secret
        self._service_identity = service_identity
        self._timeout_seconds = timeout_seconds

        self._loop: asyncio.AbstractEventLoop | None = None
        self._loop_thread: Thread | None = None
        self._nc: NATSClient | None = None
        self._token: str | None = None
        self._token_expires_at: datetime | None = None
        # Guards connect/reconnect + token bookkeeping on the persistent
        # loop, mirroring NATSJetStreamAdapter.__publish_lock.
        self._call_lock = RLock()

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()
        return False

    def close(self) -> None:
        with self._call_lock:
            self._close_connection()
            self._stop_loop()

    # ------------------------------------------------------------------
    # Persistent background event loop, same shape as NATSJetStreamAdapter.
    # ------------------------------------------------------------------

    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        if self._loop is not None and self._loop.is_running():
            return self._loop

        ready = ThreadingEvent()
        holder: dict[str, asyncio.AbstractEventLoop] = {}

        def _run() -> None:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            holder["loop"] = loop
            ready.set()
            loop.run_forever()
            loop.close()

        thread = Thread(
            target=_run,
            daemon=True,
            name="object-storage-nats-client-loop",
        )
        thread.start()
        ready.wait()
        self._loop = holder["loop"]
        self._loop_thread = thread
        return self._loop

    def _run_coro(self, coro, timeout: float | None = None):
        loop = self._ensure_loop()
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result(timeout=timeout or self._timeout_seconds)

    def _stop_loop(self) -> None:
        loop = self._loop
        thread = self._loop_thread
        self._loop = None
        self._loop_thread = None
        if loop is not None:
            loop.call_soon_threadsafe(loop.stop)
        if thread is not None:
            thread.join(timeout=5.0)

    async def _ensure_connection_async(self) -> NATSClient:
        if self._nc is not None and self._nc.is_connected:
            return self._nc
        nc = await nats.connect(self._nats_url)
        self._nc = nc
        return nc

    def _close_connection(self) -> None:
        nc = self._nc
        self._nc = None
        if nc is not None and self._loop is not None and self._loop.is_running():
            try:
                self._run_coro(nc.close(), timeout=5.0)
            except Exception:  # noqa: BLE001
                # Best-effort close of a connection we're discarding anyway
                # (already stale, or being replaced by a fresh reconnect).
                logger.opt(exception=True).debug(
                    "ObjectStorageSecondaryAdapterNATSClient: error closing stale connection"
                )

    # ------------------------------------------------------------------
    # Auth: issue once, reissue only when close to expiry.
    # ------------------------------------------------------------------

    def _current_token(self) -> str:
        now = datetime.now(UTC)
        if (
            self._token is None
            or self._token_expires_at is None
            or now >= self._token_expires_at - _TOKEN_RENEWAL_MARGIN
        ):
            self._token = issue_service_token(self._service_identity, self._jwt_secret)
            self._token_expires_at = now + DEFAULT_TTL
        return self._token

    # ------------------------------------------------------------------
    # RPC plumbing.
    # ------------------------------------------------------------------

    def _context(self) -> common_pb2.CallContext:
        return common_pb2.CallContext(
            trace_id=str(uuid.uuid4()),
            timeout_ms=int(self._timeout_seconds * 1000),
        )

    def _call(
        self, subject: str, request: Message, response_cls: type[_ResponseT]
    ) -> _ResponseT:
        payload = request.SerializeToString()
        with self._call_lock:
            headers = {AUTH_HEADER: self._current_token()}
            try:
                msg = self._run_coro(self._do_request_async(subject, payload, headers))
            except Exception:  # noqa: BLE001
                self._close_connection()
                try:
                    msg = self._run_coro(
                        self._do_request_async(subject, payload, headers)
                    )
                except Exception as exc:
                    self._close_connection()
                    raise ConnectionError(
                        f"object_storage NATS RPC to {subject!r} failed"
                    ) from exc

        response = response_cls()
        response.ParseFromString(msg.data)
        return response

    async def _do_request_async(self, subject: str, payload: bytes, headers: dict[str, str]):
        nc = await self._ensure_connection_async()
        return await nc.request(
            subject, payload, timeout=self._timeout_seconds, headers=headers
        )

    # ------------------------------------------------------------------
    # IObjectStorageAdapter.
    # ------------------------------------------------------------------

    def get_object(self, prefix: str, key: str) -> bytes:
        request = object_storage_pb2.GetObjectRequest(
            context=self._context(), prefix=prefix, key=key
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.get_object", request, object_storage_pb2.GetObjectResponse
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
            f"{SUBJECT_PREFIX}.put_object", request, object_storage_pb2.PutObjectResponse
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
