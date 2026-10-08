"""NATS RPC client adapter for the keyvalue kernel domain.

Implements ``IKeyValueAdapter`` by calling out to a remote
``KeyValuePrimaryAdapterNATS`` over NATS request/reply -- see
``naas_abi_core/proto/keyvalue/v1/keyvalue.proto`` for the wire contract and
``naas_abi_core/proto/README.md`` for why it lives there.

Shared connection, token, timeout, and reply handling live in
``naas_abi_core.engine.nats_rpc.NatsRPCClient``. Calls are never replayed
by the transport after failure; a timeout may hide a completed operation.

Stage 1 auth model (see ``naas_abi_core.engine.nats_auth``): a JWT asserting
``service_identity`` is issued once and attached on the ``Nats-Auth-Token``
header of every request, reissued only when it is close to expiry rather
than on every call. ``KeyValuePrimaryAdapterNATS`` must read the token from
that exact header -- both sides read ``AUTH_HEADER`` from
``keyvalue_nats_contract``, a neutral module neither adapter owns, so this
file never has to import from the primary adapter's module (or vice versa)
just to agree on a header name.

``KeyValueService.lock()`` is explicitly out of scope for this v1 contract
(see the ``.proto`` file's header comment): it isn't part of
``IKeyValueAdapter``, so there is no NATS subject for it either -- it keeps
working transparently against this adapter, composed purely from ``set``
``set_if_not_exists``/``delete_if_value_matches`` below plus a client-side
retry/backoff loop, each call simply going over the wire.
"""

from __future__ import annotations

from naas_abi_core.engine.nats_rpc import NatsRPCClient
from naas_abi_core.proto.common.v1 import common_pb2
from naas_abi_core.proto.keyvalue.v1 import keyvalue_pb2
from naas_abi_core.services.keyvalue.adapters.keyvalue_nats_contract import (
    AUTH_HEADER,
    SUBJECT_PREFIX,
)
from naas_abi_core.services.keyvalue.KeyValuePorts import (
    IKeyValueAdapter,
    KVLockTimeoutError,
    KVNotFoundError,
)


def _raise_for_error(
    error: common_pb2.CallError,
    lock_timeout_detail: keyvalue_pb2.KVLockTimeoutDetail | None = None,
) -> None:
    """Raise the exception matching ``error.code``.

    Must stay exactly symmetric with how ``KeyValuePrimaryAdapterNATS``
    encodes errors -- the generic adapter contract test asserts on the real
    exception types, not on the wire code.
    """
    if error.code == "KV_NOT_FOUND":
        raise KVNotFoundError(error.message)
    if error.code == "KV_LOCK_TIMEOUT":
        if lock_timeout_detail is not None:
            raise KVLockTimeoutError(
                key=lock_timeout_detail.key,
                attempts=lock_timeout_detail.attempts,
                timeout=lock_timeout_detail.timeout_seconds,
            )
        raise RuntimeError(f"keyvalue NATS RPC failed ({error.code}): {error.message}")
    raise RuntimeError(f"keyvalue NATS RPC failed ({error.code}): {error.message}")


class KeyValueSecondaryAdapterNATSClient(NatsRPCClient, IKeyValueAdapter):
    """Calls a remote ``KeyValuePrimaryAdapterNATS`` over NATS RPC."""

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
    # IKeyValueAdapter.
    # ------------------------------------------------------------------

    def get(self, key: str) -> bytes:
        request = keyvalue_pb2.GetRequest(context=self._context(), key=key)
        response = self._call(
            f"{SUBJECT_PREFIX}.get", request, keyvalue_pb2.GetResponse
        )
        if response.HasField("error"):
            _raise_for_error(
                response.error,
                response.lock_timeout_detail
                if response.HasField("lock_timeout_detail")
                else None,
            )
        return response.value

    def set(self, key: str, value: bytes, ttl: int | None = None) -> None:
        request = keyvalue_pb2.SetRequest(
            context=self._context(), key=key, value=value, ttl=ttl
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.set", request, keyvalue_pb2.SetResponse
        )
        if response.HasField("error"):
            _raise_for_error(
                response.error,
                response.lock_timeout_detail
                if response.HasField("lock_timeout_detail")
                else None,
            )

    def set_if_not_exists(
        self,
        key: str,
        value: bytes,
        ttl: int | None = None,
    ) -> bool:
        request = keyvalue_pb2.SetIfNotExistsRequest(
            context=self._context(), key=key, value=value, ttl=ttl
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.set_if_not_exists",
            request,
            keyvalue_pb2.SetIfNotExistsResponse,
        )
        if response.HasField("error"):
            _raise_for_error(
                response.error,
                response.lock_timeout_detail
                if response.HasField("lock_timeout_detail")
                else None,
            )
        return response.ok_value

    def delete(self, key: str) -> None:
        request = keyvalue_pb2.DeleteRequest(context=self._context(), key=key)
        response = self._call(
            f"{SUBJECT_PREFIX}.delete", request, keyvalue_pb2.DeleteResponse
        )
        if response.HasField("error"):
            _raise_for_error(
                response.error,
                response.lock_timeout_detail
                if response.HasField("lock_timeout_detail")
                else None,
            )

    def delete_if_value_matches(self, key: str, value: bytes) -> bool:
        request = keyvalue_pb2.DeleteIfValueMatchesRequest(
            context=self._context(), key=key, value=value
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.delete_if_value_matches",
            request,
            keyvalue_pb2.DeleteIfValueMatchesResponse,
        )
        if response.HasField("error"):
            _raise_for_error(
                response.error,
                response.lock_timeout_detail
                if response.HasField("lock_timeout_detail")
                else None,
            )
        return response.ok_value

    def exists(self, key: str) -> bool:
        request = keyvalue_pb2.ExistsRequest(context=self._context(), key=key)
        response = self._call(
            f"{SUBJECT_PREFIX}.exists", request, keyvalue_pb2.ExistsResponse
        )
        if response.HasField("error"):
            _raise_for_error(
                response.error,
                response.lock_timeout_detail
                if response.HasField("lock_timeout_detail")
                else None,
            )
        return response.ok_value
