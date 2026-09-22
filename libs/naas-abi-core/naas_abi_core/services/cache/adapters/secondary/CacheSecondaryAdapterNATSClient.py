"""NATS RPC client adapter for the cache kernel domain.

Implements ``ICacheAdapter`` by calling out to a remote
``CachePrimaryAdapterNATS`` over NATS request/reply -- see
``naas_abi_core/proto/cache/v1/cache.proto`` for the wire contract and
``naas_abi_core/proto/README.md`` for why it lives there.

This is a *raw tier adapter*, exactly like ``CacheFSAdapter``/
``CacheRedisAdapter``/``ObjectStorageBackedAdapter``: it implements
``ICacheAdapter``'s five methods only, nothing about tiering or event
publishing. Plug it into a ``CacheAdapterEntry`` (one entry = one tier) the
same way any other cache adapter plugs in -- ``SingleTierCacheService``/
``CacheService`` wrap it exactly as they would a local adapter, and all
tiering + event-publishing behaviour keeps running unaffected on whichever
machine loads that tier's config, this client included.

Shared connection, token, timeout, and reply handling live in
``naas_abi_core.engine.nats_rpc.NatsRPCClient``. Calls are never replayed
by the transport after failure; a timeout may hide a completed operation.

Stage 1 auth model (see ``naas_abi_core.engine.nats_auth``): a JWT asserting
``service_identity`` is issued once and attached on the ``Nats-Auth-Token``
header of every request, reissued only when it is close to expiry rather
than on every call. ``CachePrimaryAdapterNATS`` must read the token from
that exact header -- both sides read ``AUTH_HEADER`` from
``cache_nats_contract``, a neutral module neither adapter owns, so this file
never has to import from the primary adapter's module (or vice versa) just
to agree on a header name.
"""

from __future__ import annotations

from naas_abi_core.engine.nats_rpc import NatsRPCClient
from naas_abi_core.proto.cache.v1 import cache_pb2
from naas_abi_core.proto.common.v1 import common_pb2
from naas_abi_core.services.cache.adapters.cache_nats_contract import (
    AUTH_HEADER,
    SUBJECT_PREFIX,
)
from naas_abi_core.services.cache.CachePort import (
    CachedData,
    CacheExpiredError,
    CacheNotFoundError,
    DataType,
    ICacheAdapter,
)

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


def _raise_for_error(error: common_pb2.CallError) -> None:
    """Raise the exception matching ``error.code``.

    Must stay exactly symmetric with how ``CachePrimaryAdapterNATS`` encodes
    errors -- the integration test asserts on the real exception types, not
    on the wire code.
    """
    if error.code == "CACHE_NOT_FOUND":
        raise CacheNotFoundError(error.message)
    if error.code == "CACHE_EXPIRED":
        raise CacheExpiredError(error.message)
    raise RuntimeError(f"cache NATS RPC failed ({error.code}): {error.message}")


class CacheSecondaryAdapterNATSClient(NatsRPCClient, ICacheAdapter):
    """Calls a remote ``CachePrimaryAdapterNATS`` over NATS RPC."""

    def __init__(
        self,
        nats_url: str,
        jwt_secret: str,
        service_identity: str,
        timeout_seconds: float = 10.0,
        *,
        subject_prefix: str = SUBJECT_PREFIX,
    ) -> None:
        self._subject_prefix = subject_prefix
        super().__init__(
            nats_url,
            jwt_secret,
            service_identity,
            timeout_seconds,
            auth_header=AUTH_HEADER,
        )

    # ------------------------------------------------------------------
    # ICacheAdapter.
    # ------------------------------------------------------------------

    def get(self, key: str) -> CachedData:
        request = cache_pb2.GetRequest(context=self._context(), key=key)
        response = self._call(
            f"{self._subject_prefix}.get", request, cache_pb2.GetResponse
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        return _pb_to_cached_data(response.value)

    def set(self, key: str, value: CachedData) -> None:
        request = cache_pb2.SetRequest(
            context=self._context(), key=key, value=_cached_data_to_pb(value)
        )
        response = self._call(
            f"{self._subject_prefix}.set", request, cache_pb2.SetResponse
        )
        if response.HasField("error"):
            _raise_for_error(response.error)

    def set_if_absent(self, key: str, value: CachedData) -> bool:
        request = cache_pb2.SetIfAbsentRequest(
            context=self._context(), key=key, value=_cached_data_to_pb(value)
        )
        response = self._call(
            f"{self._subject_prefix}.set_if_absent",
            request,
            cache_pb2.SetIfAbsentResponse,
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        return response.value

    def delete(self, key: str) -> None:
        request = cache_pb2.DeleteRequest(context=self._context(), key=key)
        response = self._call(
            f"{self._subject_prefix}.delete", request, cache_pb2.DeleteResponse
        )
        if response.HasField("error"):
            _raise_for_error(response.error)

    def exists(self, key: str) -> bool:
        request = cache_pb2.ExistsRequest(context=self._context(), key=key)
        response = self._call(
            f"{self._subject_prefix}.exists", request, cache_pb2.ExistsResponse
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        return response.value
