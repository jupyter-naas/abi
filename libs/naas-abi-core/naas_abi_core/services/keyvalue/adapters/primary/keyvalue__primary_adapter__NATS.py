"""NATS RPC primary adapter for the keyvalue kernel domain.

Exposes a real ``IKeyValueAdapter`` as a NATS micro-service (see
``naas_abi_core/proto/keyvalue/v1/keyvalue.proto`` for the wire contract and
``naas_abi_core/proto/README.md`` for why it lives there). This is the server
side; the matching client is ``KeyValueSecondaryAdapterNATSClient``.

Stage 1 auth model (see ``naas_abi_core.engine.nats_auth``): one shared
secret, one claim -- which known first-party process holds the token. Every
incoming request must carry a valid token in the ``Nats-Auth-Token`` header
(``AUTH_HEADER``, imported from ``keyvalue_nats_contract`` below -- that's a
neutral module neither adapter owns, so this file and the client's don't
depend on each other; see that module's docstring for why).

``KeyValueService.lock()`` is explicitly out of scope for this v1 contract
(see the ``.proto`` file's header comment): it composes purely from
``set_if_not_exists``/``delete_if_value_matches`` plus a client-side
retry/backoff loop, isn't part of ``IKeyValueAdapter``, and so has no
endpoint here at all -- it keeps working transparently once
``KeyValueSecondaryAdapterNATSClient`` is plugged in, with each of its two
calls simply going over the wire.
"""

from __future__ import annotations

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
from naas_abi_core.proto.common.v1 import common_pb2
from naas_abi_core.proto.keyvalue.v1 import keyvalue_pb2
from naas_abi_core.services.keyvalue.adapters.keyvalue_nats_contract import (
    AUTH_HEADER,
    SERVICE_NAME,
    SERVICE_VERSION,
    SUBJECT_PREFIX,
)
from naas_abi_core.services.keyvalue.KeyValuePorts import (
    IKeyValueAdapter,
    KVLockTimeoutError,
    KVNotFoundError,
)
from naas_abi_core.services.keyvalue.KeyValueService import KeyValueService
from nats.micro.request import Request
from nats.micro.service import Service

__all__ = [
    "AUTH_HEADER",
    "SERVICE_NAME",
    "SERVICE_VERSION",
    "SUBJECT_PREFIX",
    "KeyValuePrimaryAdapterNATS",
]

_RequestT = TypeVar("_RequestT", bound=Message)
_ResponseT = TypeVar("_ResponseT", bound=Message)


class KeyValuePrimaryAdapterNATS:
    """Serves keyvalue over NATS RPC (request/reply).

    Wraps a real adapter *or* the domain service and registers one NATS
    micro-service endpoint per ``IKeyValueAdapter`` method. Each endpoint
    authenticates the caller via ``Nats-Auth-Token`` before doing anything
    else, then decodes the Protobuf request, calls straight through to the
    wrapped object, and encodes a Protobuf response. Errors -- auth
    failures, known domain exceptions, anything unexpected -- are always
    reported as a normal response carrying a populated ``CallError``, never
    as a crashed handler or a raw NATS-level error.

    Accepts either an ``IKeyValueAdapter`` (a bare secondary adapter, e.g. in
    tests) or a ``KeyValueService`` (the real engine-loaded domain service)
    -- deliberately, not for convenience: wrapping the raw adapter instead of
    the domain service would silently skip ``KeyValueService``'s event
    publishing (``KeyValueSet``/``KeyValueDeleted``/``KeyValueError``) for
    every remote caller, which would only diverge from in-process behaviour,
    not match it. ``EngineNATSLoader`` always passes the domain service.
    """

    def __init__(
        self,
        adapter: IKeyValueAdapter | KeyValueService,
        jwt_secret: str,
    ) -> None:
        self._adapter = adapter
        self._jwt_secret = jwt_secret
        self._dispatch = DomainRPCDispatcher(SERVICE_NAME)
        self._service: Service | None = None

    async def start(self, nc: nats.NATS) -> None:
        """Register the ``keyvalue`` NATS service on ``nc``.

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
            description="ABI kernel keyvalue domain, exposed over NATS RPC (v1).",
        )
        await service.add_endpoint(
            name="get",
            subject=f"{SUBJECT_PREFIX}.get",
            handler=self._handle_get,
        )
        await service.add_endpoint(
            name="set",
            subject=f"{SUBJECT_PREFIX}.set",
            handler=self._handle_set,
        )
        await service.add_endpoint(
            name="set_if_not_exists",
            subject=f"{SUBJECT_PREFIX}.set_if_not_exists",
            handler=self._handle_set_if_not_exists,
        )
        await service.add_endpoint(
            name="delete",
            subject=f"{SUBJECT_PREFIX}.delete",
            handler=self._handle_delete,
        )
        await service.add_endpoint(
            name="delete_if_value_matches",
            subject=f"{SUBJECT_PREFIX}.delete_if_value_matches",
            handler=self._handle_delete_if_value_matches,
        )
        await service.add_endpoint(
            name="exists",
            subject=f"{SUBJECT_PREFIX}.exists",
            handler=self._handle_exists,
        )
        self._service = service

    async def stop(self) -> None:
        """Deregister the service, draining its subscriptions."""
        service = self._service
        self._service = None
        try:
            if service is not None:
                await service.stop()
        finally:
            self._dispatch.close()

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
        except KVNotFoundError as exc:
            await self._respond_error(
                request, response_cls, "KV_NOT_FOUND", str(exc), retryable=False
            )
            return
        except KVLockTimeoutError as exc:
            await self._respond_error(
                request,
                response_cls,
                "KV_LOCK_TIMEOUT",
                str(exc),
                retryable=True,
                lock_timeout_detail=keyvalue_pb2.KVLockTimeoutDetail(
                    key=exc.key, attempts=exc.attempts, timeout_seconds=exc.timeout
                ),
            )
            return
        except Exception:  # noqa: BLE001 - a handler must never crash the service
            logger.opt(exception=True).error(
                f"KeyValuePrimaryAdapterNATS: unexpected error handling {request.subject!r}"
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
        lock_timeout_detail: keyvalue_pb2.KVLockTimeoutDetail | None = None,
    ) -> None:
        kwargs: dict[str, object] = {
            "error": common_pb2.CallError(
                code=code, message=message, retryable=retryable
            )
        }
        if lock_timeout_detail is not None:
            kwargs["lock_timeout_detail"] = lock_timeout_detail
        response = response_cls(**kwargs)
        await respond_protobuf(request, response, response_cls)

    # ------------------------------------------------------------------
    # Endpoint handlers -- one per IKeyValueAdapter method.
    # ------------------------------------------------------------------

    async def _handle_get(self, request: Request) -> None:
        await self._handle(
            request,
            keyvalue_pb2.GetRequest,
            keyvalue_pb2.GetResponse,
            self._call_get,
        )

    def _call_get(self, req: keyvalue_pb2.GetRequest) -> keyvalue_pb2.GetResponse:
        value = self._adapter.get(req.key)
        return keyvalue_pb2.GetResponse(value=value)

    async def _handle_set(self, request: Request) -> None:
        await self._handle(
            request,
            keyvalue_pb2.SetRequest,
            keyvalue_pb2.SetResponse,
            self._call_set,
        )

    def _call_set(self, req: keyvalue_pb2.SetRequest) -> keyvalue_pb2.SetResponse:
        ttl = req.ttl if req.HasField("ttl") else None
        self._adapter.set(req.key, req.value, ttl)
        return keyvalue_pb2.SetResponse()

    async def _handle_set_if_not_exists(self, request: Request) -> None:
        await self._handle(
            request,
            keyvalue_pb2.SetIfNotExistsRequest,
            keyvalue_pb2.SetIfNotExistsResponse,
            self._call_set_if_not_exists,
        )

    def _call_set_if_not_exists(
        self, req: keyvalue_pb2.SetIfNotExistsRequest
    ) -> keyvalue_pb2.SetIfNotExistsResponse:
        ttl = req.ttl if req.HasField("ttl") else None
        wrote = self._adapter.set_if_not_exists(req.key, req.value, ttl)
        return keyvalue_pb2.SetIfNotExistsResponse(ok_value=wrote)

    async def _handle_delete(self, request: Request) -> None:
        await self._handle(
            request,
            keyvalue_pb2.DeleteRequest,
            keyvalue_pb2.DeleteResponse,
            self._call_delete,
        )

    def _call_delete(
        self, req: keyvalue_pb2.DeleteRequest
    ) -> keyvalue_pb2.DeleteResponse:
        self._adapter.delete(req.key)
        return keyvalue_pb2.DeleteResponse()

    async def _handle_delete_if_value_matches(self, request: Request) -> None:
        await self._handle(
            request,
            keyvalue_pb2.DeleteIfValueMatchesRequest,
            keyvalue_pb2.DeleteIfValueMatchesResponse,
            self._call_delete_if_value_matches,
        )

    def _call_delete_if_value_matches(
        self, req: keyvalue_pb2.DeleteIfValueMatchesRequest
    ) -> keyvalue_pb2.DeleteIfValueMatchesResponse:
        deleted = self._adapter.delete_if_value_matches(req.key, req.value)
        return keyvalue_pb2.DeleteIfValueMatchesResponse(ok_value=deleted)

    async def _handle_exists(self, request: Request) -> None:
        await self._handle(
            request,
            keyvalue_pb2.ExistsRequest,
            keyvalue_pb2.ExistsResponse,
            self._call_exists,
        )

    def _call_exists(
        self, req: keyvalue_pb2.ExistsRequest
    ) -> keyvalue_pb2.ExistsResponse:
        exists = self._adapter.exists(req.key)
        return keyvalue_pb2.ExistsResponse(ok_value=exists)
