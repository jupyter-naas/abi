"""NATS RPC primary adapter for the cache kernel domain.

Exposes a real ``ICacheAdapter`` as a NATS micro-service (see
``naas_abi_core/proto/cache/v1/cache.proto`` for the wire contract and
``naas_abi_core/proto/README.md`` for why it lives there). This is the
server side; the matching client is ``CacheSecondaryAdapterNATSClient``.

Unlike ``object_storage``, this adapter wraps the raw ``ICacheAdapter`` --
never ``SingleTierCacheService``/``CacheService`` -- and that is a deliberate
choice, not an oversight: reading ``SingleTierCacheService`` shows that
``event_publisher`` (and tiering) is layered entirely *outside* the
``ICacheAdapter`` boundary. ``SingleTierCacheService`` calls the raw
adapter's five methods (``get``/``set``/``set_if_absent``/``delete``/
``exists``) and does its own event publication (``CacheSet``/
``CacheDeleted``/``CacheError``) and TTL/tier bookkeeping around that --
nothing the adapter itself needs to know about, and nothing that changes
adapter-level behaviour. So wrapping the raw adapter here is correct: the
tiering + eventing logic keeps running unaffected wherever a tier's config
is loaded, including on the machine holding the NATS client adapter for
this contract -- there is no ``ICacheDomain`` layer to preserve, the way
``ObjectStoragePrimaryAdapterNATS`` has to accept an ``IObjectStorageDomain``
to keep its event publishing intact.

Stage 1 auth model (see ``naas_abi_core.engine.nats_auth``): one shared
secret, one claim -- which known first-party process holds the token. Every
incoming request must carry a valid token in the ``Nats-Auth-Token`` header
(``AUTH_HEADER``, imported from ``cache_nats_contract`` below -- that's a
neutral module neither adapter owns, so this file and the client's don't
depend on each other; see that module's docstring for why).
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
from naas_abi_core.proto.cache.v1 import cache_pb2
from naas_abi_core.proto.common.v1 import common_pb2
from naas_abi_core.services.cache.adapters.cache_nats_contract import (
    AUTH_HEADER,
    SERVICE_NAME,
    SERVICE_VERSION,
    SUBJECT_PREFIX,
)
from naas_abi_core.services.cache.CachePort import (
    CachedData,
    CacheExpiredError,
    CacheNotFoundError,
    DataType,
    ICacheAdapter,
)
from nats.micro.request import Request
from nats.micro.service import Service

__all__ = [
    "AUTH_HEADER",
    "SERVICE_NAME",
    "SERVICE_VERSION",
    "SUBJECT_PREFIX",
    "CachePrimaryAdapterNATS",
]

_RequestT = TypeVar("_RequestT", bound=Message)
_ResponseT = TypeVar("_ResponseT", bound=Message)

_DATA_TYPE_TO_PB: dict[DataType, cache_pb2.DataType] = {
    DataType.TEXT: cache_pb2.DATA_TYPE_TEXT,
    DataType.JSON: cache_pb2.DATA_TYPE_JSON,
    DataType.BINARY: cache_pb2.DATA_TYPE_BINARY,
    DataType.PICKLE: cache_pb2.DATA_TYPE_PICKLE,
}
_PB_TO_DATA_TYPE: dict[int, DataType] = {
    pb_value: data_type for data_type, pb_value in _DATA_TYPE_TO_PB.items()
}


def _cached_data_to_pb(data: CachedData) -> cache_pb2.CachedData:
    return cache_pb2.CachedData(
        key=data.key,
        data=data.data,
        data_type=_DATA_TYPE_TO_PB[data.data_type],
        created_at=data.created_at,
    )


def _pb_to_cached_data(pb: cache_pb2.CachedData) -> CachedData:
    return CachedData(
        key=pb.key,
        data=pb.data,
        data_type=_PB_TO_DATA_TYPE[pb.data_type],
        created_at=pb.created_at,
    )


class CachePrimaryAdapterNATS:
    """Serves one cache tier's ``ICacheAdapter`` over NATS RPC (request/reply).

    Registers one NATS micro-service endpoint per ``ICacheAdapter`` method.
    Each endpoint authenticates the caller via ``Nats-Auth-Token`` before
    doing anything else, then decodes the Protobuf request, calls straight
    through to the wrapped adapter, and encodes a Protobuf response. Errors
    -- auth failures, known domain exceptions, anything unexpected -- are
    always reported as a normal response carrying a populated ``CallError``,
    never as a crashed handler or a raw NATS-level error.
    """

    def __init__(
        self,
        adapter: ICacheAdapter,
        jwt_secret: str,
        *,
        subject_prefix: str = SUBJECT_PREFIX,
        tiers: tuple[str, ...] = (),
    ) -> None:
        self._subject_prefix = subject_prefix
        self._tiers = tiers
        self._adapter = adapter
        self._jwt_secret = jwt_secret
        self._dispatch = DomainRPCDispatcher(SERVICE_NAME)
        self._service: Service | None = None

    async def start(self, nc: nats.NATS) -> None:
        """Register the ``cache`` NATS service on ``nc``.

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
            description="ABI kernel cache domain, exposed over NATS RPC (v1).",
        )
        await service.add_endpoint(
            name="get",
            subject=f"{self._subject_prefix}.get",
            handler=self._handle_get,
        )
        await service.add_endpoint(
            name="set",
            subject=f"{self._subject_prefix}.set",
            handler=self._handle_set,
        )
        await service.add_endpoint(
            name="set_if_absent",
            subject=f"{self._subject_prefix}.set_if_absent",
            handler=self._handle_set_if_absent,
        )
        await service.add_endpoint(
            name="delete",
            subject=f"{self._subject_prefix}.delete",
            handler=self._handle_delete,
        )
        await service.add_endpoint(
            name="exists",
            subject=f"{self._subject_prefix}.exists",
            handler=self._handle_exists,
        )
        await service.add_endpoint(
            name="describe",
            subject=f"{self._subject_prefix}.describe",
            handler=self._handle_describe,
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
        except CacheNotFoundError as exc:
            await self._respond_error(
                request, response_cls, "CACHE_NOT_FOUND", str(exc), retryable=False
            )
            return
        except CacheExpiredError as exc:
            await self._respond_error(
                request, response_cls, "CACHE_EXPIRED", str(exc), retryable=False
            )
            return
        except Exception:  # noqa: BLE001 - a handler must never crash the service
            logger.opt(exception=True).error(
                f"CachePrimaryAdapterNATS: unexpected error handling {request.subject!r}"
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
    # Endpoint handlers -- one per ICacheAdapter method.
    # ------------------------------------------------------------------

    async def _handle_get(self, request: Request) -> None:
        await self._handle(
            request,
            cache_pb2.GetRequest,
            cache_pb2.GetResponse,
            self._call_get,
        )

    def _call_get(self, req: cache_pb2.GetRequest) -> cache_pb2.GetResponse:
        data = self._adapter.get(req.key)
        return cache_pb2.GetResponse(value=_cached_data_to_pb(data))

    async def _handle_set(self, request: Request) -> None:
        await self._handle(
            request,
            cache_pb2.SetRequest,
            cache_pb2.SetResponse,
            self._call_set,
        )

    def _call_set(self, req: cache_pb2.SetRequest) -> cache_pb2.SetResponse:
        self._adapter.set(req.key, _pb_to_cached_data(req.value))
        return cache_pb2.SetResponse()

    async def _handle_set_if_absent(self, request: Request) -> None:
        await self._handle(
            request,
            cache_pb2.SetIfAbsentRequest,
            cache_pb2.SetIfAbsentResponse,
            self._call_set_if_absent,
        )

    def _call_set_if_absent(
        self, req: cache_pb2.SetIfAbsentRequest
    ) -> cache_pb2.SetIfAbsentResponse:
        wrote = self._adapter.set_if_absent(req.key, _pb_to_cached_data(req.value))
        return cache_pb2.SetIfAbsentResponse(value=wrote)

    async def _handle_delete(self, request: Request) -> None:
        await self._handle(
            request,
            cache_pb2.DeleteRequest,
            cache_pb2.DeleteResponse,
            self._call_delete,
        )

    def _call_delete(self, req: cache_pb2.DeleteRequest) -> cache_pb2.DeleteResponse:
        self._adapter.delete(req.key)
        return cache_pb2.DeleteResponse()

    async def _handle_exists(self, request: Request) -> None:
        await self._handle(
            request,
            cache_pb2.ExistsRequest,
            cache_pb2.ExistsResponse,
            self._call_exists,
        )

    def _call_exists(self, req: cache_pb2.ExistsRequest) -> cache_pb2.ExistsResponse:
        exists = self._adapter.exists(req.key)
        return cache_pb2.ExistsResponse(value=exists)

    async def _handle_describe(self, request: Request) -> None:
        await self._handle(
            request,
            cache_pb2.DescribeRequest,
            cache_pb2.DescribeResponse,
            lambda _: cache_pb2.DescribeResponse(tiers=self._tiers),
        )
