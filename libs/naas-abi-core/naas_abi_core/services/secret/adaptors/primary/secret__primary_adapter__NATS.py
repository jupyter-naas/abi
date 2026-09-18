"""NATS RPC primary adapter for the secret kernel domain.

Exposes a real ``ISecretAdapter`` (or, for the real deployed case, the
``Secret`` domain facade fanning out over several of them) as a NATS
micro-service (see ``naas_abi_core/proto/secret/v1/secret.proto`` for the
wire contract and ``naas_abi_core/proto/README.md`` for why it lives
there). This is the server side; the matching client is
``SecretSecondaryAdapterNATSClient``.

Security note: Stage 1's shared-JWT auth (``naas_abi_core.engine.nats_auth``)
has no per-caller ARN/IAM authorization -- see
``secret_nats_contract.py``'s docstring. Ported anyway, an explicit,
accepted, temporary gap, not an oversight.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

import nats
import nats.micro
from google.protobuf.message import Message
from naas_abi_core import logger
from naas_abi_core.engine.nats_auth import (
    InvalidServiceTokenError,
    verify_service_token,
)
from naas_abi_core.proto.common.v1 import common_pb2
from naas_abi_core.proto.secret.v1 import secret_pb2
from naas_abi_core.services.secret.adaptors.secret_nats_contract import (
    AUTH_HEADER,
    SERVICE_NAME,
    SERVICE_VERSION,
    SUBJECT_PREFIX,
)
from naas_abi_core.services.secret.Secret import Secret
from naas_abi_core.services.secret.SecretPorts import (
    ISecretAdapter,
    SecretAuthenticationError,
)
from nats.micro.request import Request
from nats.micro.service import Service

__all__ = [
    "AUTH_HEADER",
    "SERVICE_NAME",
    "SERVICE_VERSION",
    "SUBJECT_PREFIX",
    "SecretPrimaryAdapterNATS",
]

_RequestT = TypeVar("_RequestT", bound=Message)
_ResponseT = TypeVar("_ResponseT", bound=Message)


class SecretPrimaryAdapterNATS:
    """Serves secrets over NATS RPC (request/reply).

    Wraps a real ``ISecretAdapter`` *or* the domain ``Secret`` facade and
    registers one NATS micro-service endpoint per ``ISecretAdapter``
    method. Each endpoint authenticates the caller via ``Nats-Auth-Token``
    before doing anything else, then decodes the Protobuf request, calls
    straight through to the wrapped object, and encodes a Protobuf
    response. Errors -- auth failures, known domain exceptions, anything
    unexpected -- are always reported as a normal response carrying a
    populated ``CallError``, never as a crashed handler or a raw NATS-level
    error.

    Accepts either an ``ISecretAdapter`` (a bare secondary adapter, e.g. in
    tests) or a ``Secret`` (the real engine-loaded domain service) --
    deliberately, not for convenience: wrapping a single raw adapter
    instead of ``Secret`` would silently skip ``Secret``'s fan-out across
    every configured adapter (dotenv/naas/base64/...) and its
    ``SecretSet``/``SecretRemoved``/``SecretError`` event publishing for
    every remote caller, which would only diverge from in-process
    behaviour, not match it. ``EngineNATSLoader`` always passes the domain
    service.
    """

    def __init__(
        self,
        adapter: ISecretAdapter | Secret,
        jwt_secret: str,
    ) -> None:
        self._adapter = adapter
        self._jwt_secret = jwt_secret
        self._service: Service | None = None

    async def start(self, nc: nats.NATS) -> None:
        """Register the ``secret`` NATS service on ``nc``.

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
            description="ABI kernel secret domain, exposed over NATS RPC (v1).",
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
            name="remove",
            subject=f"{SUBJECT_PREFIX}.remove",
            handler=self._handle_remove,
        )
        await service.add_endpoint(
            name="list",
            subject=f"{SUBJECT_PREFIX}.list",
            handler=self._handle_list,
        )
        self._service = service

    async def stop(self) -> None:
        """Deregister the service, draining its subscriptions."""
        service = self._service
        self._service = None
        if service is not None:
            await service.stop()

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
        parsed_request.ParseFromString(request.data)

        try:
            response = call(parsed_request)
        except SecretAuthenticationError as exc:
            await self._respond_error(
                request, response_cls, "SECRET_AUTH_FAILED", str(exc), retryable=False
            )
            return
        except Exception:  # noqa: BLE001 - a handler must never crash the service
            logger.opt(exception=True).error(
                f"SecretPrimaryAdapterNATS: unexpected error handling {request.subject!r}"
            )
            await self._respond_error(
                request, response_cls, "INTERNAL", "internal error", retryable=True
            )
            return

        await request.respond(response.SerializeToString())

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
        await request.respond(response.SerializeToString())

    # ------------------------------------------------------------------
    # Endpoint handlers -- one per ISecretAdapter method.
    # ------------------------------------------------------------------

    async def _handle_get(self, request: Request) -> None:
        await self._handle(
            request, secret_pb2.GetRequest, secret_pb2.GetResponse, self._call_get
        )

    def _call_get(self, req: secret_pb2.GetRequest) -> secret_pb2.GetResponse:
        # No `default` argument here -- see secret.proto's header comment:
        # the client applies its caller's default locally when unset.
        value = self._adapter.get(req.key, None)
        result = secret_pb2.GetResult()
        if value is not None:
            result.value = str(value)
        return secret_pb2.GetResponse(found=result)

    async def _handle_set(self, request: Request) -> None:
        await self._handle(
            request, secret_pb2.SetRequest, secret_pb2.SetResponse, self._call_set
        )

    def _call_set(self, req: secret_pb2.SetRequest) -> secret_pb2.SetResponse:
        self._adapter.set(req.key, req.value)
        return secret_pb2.SetResponse()

    async def _handle_remove(self, request: Request) -> None:
        await self._handle(
            request,
            secret_pb2.RemoveRequest,
            secret_pb2.RemoveResponse,
            self._call_remove,
        )

    def _call_remove(self, req: secret_pb2.RemoveRequest) -> secret_pb2.RemoveResponse:
        self._adapter.remove(req.key)
        return secret_pb2.RemoveResponse()

    async def _handle_list(self, request: Request) -> None:
        await self._handle(
            request, secret_pb2.ListRequest, secret_pb2.ListResponse, self._call_list
        )

    def _call_list(self, req: secret_pb2.ListRequest) -> secret_pb2.ListResponse:
        secrets = self._adapter.list()
        entries = []
        for key, value in secrets.items():
            entry = secret_pb2.SecretEntry(key=key)
            if value is not None:
                entry.value = value
            entries.append(entry)
        return secret_pb2.ListResponse(found=secret_pb2.ListResult(entries=entries))
