"""NATS RPC client adapter for the secret kernel domain.

Implements ``ISecretAdapter`` by calling out to a remote
``SecretPrimaryAdapterNATS`` over NATS request/reply -- see
``naas_abi_core/proto/secret/v1/secret.proto`` for the wire contract and
``naas_abi_core/proto/README.md`` for why it lives there.

Security note: Stage 1's shared-JWT auth has no per-caller authorization --
see ``secret_nats_contract.py``'s docstring. Ported anyway, an explicit,
accepted, temporary gap.

Shared connection, token, timeout, and reply handling live in
``naas_abi_core.engine.nats_rpc.NatsRPCClient``. Calls are never replayed
after transport failure; a timeout may hide a completed operation.

Plugs into ``Secret``'s existing multi-adapter fan-out exactly like
``dotenv``/``naas``/``base64`` already do: add ``{adapter: "nats_rpc",
config: {...}}`` as one more entry in ``services.secret.secret_adapters``.
"""

from __future__ import annotations

from typing import Any

from naas_abi_core.engine.nats_rpc import NatsRPCClient
from naas_abi_core.proto.common.v1 import common_pb2
from naas_abi_core.proto.secret.v1 import secret_pb2
from naas_abi_core.services.secret.adaptors.secret_nats_contract import (
    AUTH_HEADER,
    SUBJECT_PREFIX,
)
from naas_abi_core.services.secret.SecretPorts import (
    ISecretAdapter,
    SecretAuthenticationError,
)


def _raise_for_error(error: common_pb2.CallError) -> None:
    """Raise the exception matching ``error.code``.

    Must stay exactly symmetric with how ``SecretPrimaryAdapterNATS``
    encodes errors.
    """
    if error.code == "SECRET_AUTH_FAILED":
        raise SecretAuthenticationError(error.message)
    raise RuntimeError(f"secret NATS RPC failed ({error.code}): {error.message}")


class SecretSecondaryAdapterNATSClient(NatsRPCClient, ISecretAdapter):
    """Calls a remote ``SecretPrimaryAdapterNATS`` over NATS RPC."""

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
    # ISecretAdapter.
    # ------------------------------------------------------------------

    def get(self, key: str, default: Any = None) -> str | Any | None:
        request = secret_pb2.GetRequest(context=self._context(), key=key)
        response = self._call(f"{SUBJECT_PREFIX}.get", request, secret_pb2.GetResponse)
        if response.HasField("error"):
            _raise_for_error(response.error)
        if response.found.HasField("value"):
            return response.found.value
        return default

    def set(self, key: str, value: str) -> None:
        request = secret_pb2.SetRequest(context=self._context(), key=key, value=value)
        response = self._call(f"{SUBJECT_PREFIX}.set", request, secret_pb2.SetResponse)
        if response.HasField("error"):
            _raise_for_error(response.error)

    def remove(self, key: str) -> None:
        request = secret_pb2.RemoveRequest(context=self._context(), key=key)
        response = self._call(
            f"{SUBJECT_PREFIX}.remove", request, secret_pb2.RemoveResponse
        )
        if response.HasField("error"):
            _raise_for_error(response.error)

    def list(self) -> dict[str, str | None]:
        request = secret_pb2.ListRequest(context=self._context())
        response = self._call(
            f"{SUBJECT_PREFIX}.list", request, secret_pb2.ListResponse
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        return {
            entry.key: (entry.value if entry.HasField("value") else None)
            for entry in response.found.entries
        }
