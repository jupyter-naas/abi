"""NATS RPC primary adapter for the secret kernel domain.

Exposes a real ``ISecretAdapter`` (or, for the real deployed case, the
``Secret`` domain facade fanning out over several of them) as a NATS
micro-service (see ``naas_abi_core/proto/secret/v1/secret.proto`` for the
wire contract and ``naas_abi_core/proto/README.md`` for why it lives
there). This is the server side; the matching client is
``SecretSecondaryAdapterNATSClient``.

Security note: callers are authenticated (``naas_abi_core.engine.nats_auth``)
but not yet authorized per secret -- see ``secret_nats_contract.py``'s
docstring. A known, temporary gap, not an oversight -- except that this
endpoint is an allowlist: a caller other than ``engine`` and ``idp`` reaches
only the names under its own prefix, in every operation.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TypeVar

import nats
import nats.micro
from google.protobuf.message import DecodeError, Message
from naas_abi_core import logger
from naas_abi_core.engine.call_context import current_call_context
from naas_abi_core.engine.nats_auth import TokenVerifier
from naas_abi_core.engine.nats_dispatch import DomainRPCDispatcher
from naas_abi_core.engine.nats_rpc import (
    RequestPayloadError,
    authenticate_request,
    request_payload,
    respond_protobuf,
)
from naas_abi_core.engine.nats_sessions import ServicePrimary
from naas_abi_core.engine.nats_tracing import TracedService, add_traced_service
from naas_abi_core.proto.common.v1 import common_pb2
from naas_abi_core.proto.secret.v1 import secret_pb2
from naas_abi_core.services.secret.adaptors.secret_nats_contract import (
    AUTH_HEADER,
    SERVICE_NAME,
    SERVICE_VERSION,
    SUBJECT_PREFIX,
    may_use,
)
from naas_abi_core.services.secret.Secret import Secret
from naas_abi_core.services.secret.SecretPorts import (
    ISecretAdapter,
    SecretAuthenticationError,
)
from nats.micro.request import Request

__all__ = [
    "AUTH_HEADER",
    "SERVICE_NAME",
    "SERVICE_VERSION",
    "SUBJECT_PREFIX",
    "SecretPrimaryAdapterNATS",
]


class _ReservedSecretError(Exception):
    pass


def _may_use(key: str) -> bool:
    """Whether the verified caller owns ``key`` (``secret_nats_contract.may_use``)."""
    principal = current_call_context().principal
    return may_use(principal.kind, principal.name or principal.id, key)


def _checked(key: str) -> str:
    if not _may_use(key):
        raise _ReservedSecretError(key)
    return key


_RequestT = TypeVar("_RequestT", bound=Message)
_ResponseT = TypeVar("_ResponseT", bound=Message)


class SecretPrimaryAdapterNATS(ServicePrimary):
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
        verifier: TokenVerifier,
    ) -> None:
        self._adapter = adapter
        self._verifier = verifier
        self._dispatch = DomainRPCDispatcher(SERVICE_NAME)
        self._service: TracedService | None = None

    async def start(self, nc: nats.NATS) -> None:
        """Register the ``secret`` NATS service on ``nc``.

        ``nc`` must already be connected -- this adapter never manages the
        connection lifecycle itself, only the service/endpoints layered on
        top of it. Calling this more than once is a no-op.
        """
        if self._service is not None:
            return

        service = await add_traced_service(
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
        caller = await authenticate_request(request, self._verifier, response_cls)
        if caller is None:
            return

        parsed_request = request_cls()
        try:
            parsed_request.ParseFromString(await request_payload(request))
        except RequestPayloadError as exc:
            await self._respond_error(
                request, response_cls, exc.code, exc.message, retryable=False
            )
            return
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
            response = await self._dispatch.call(call, parsed_request, caller)
        except SecretAuthenticationError as exc:
            await self._respond_error(
                request, response_cls, "SECRET_AUTH_FAILED", str(exc), retryable=False
            )
            return
        except _ReservedSecretError:
            await self._respond_error(
                request,
                response_cls,
                "PERMISSION_DENIED",
                "this secret is not the caller's",
                retryable=False,
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

        await respond_protobuf(request, response, response_cls)

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
    # Endpoint handlers -- one per ISecretAdapter method.
    # ------------------------------------------------------------------

    async def _handle_get(self, request: Request) -> None:
        await self._handle(
            request, secret_pb2.GetRequest, secret_pb2.GetResponse, self._call_get
        )

    def _call_get(self, req: secret_pb2.GetRequest) -> secret_pb2.GetResponse:
        # No `default` argument here -- see secret.proto's header comment:
        # the client applies its caller's default locally when unset.
        value = self._adapter.get(_checked(req.key), None)
        result = secret_pb2.GetResult()
        if value is not None:
            result.value = str(value)
        return secret_pb2.GetResponse(found=result)

    async def _handle_set(self, request: Request) -> None:
        await self._handle(
            request, secret_pb2.SetRequest, secret_pb2.SetResponse, self._call_set
        )

    def _call_set(self, req: secret_pb2.SetRequest) -> secret_pb2.SetResponse:
        self._adapter.set(_checked(req.key), req.value)
        return secret_pb2.SetResponse()

    async def _handle_remove(self, request: Request) -> None:
        await self._handle(
            request,
            secret_pb2.RemoveRequest,
            secret_pb2.RemoveResponse,
            self._call_remove,
        )

    def _call_remove(self, req: secret_pb2.RemoveRequest) -> secret_pb2.RemoveResponse:
        self._adapter.remove(_checked(req.key))
        return secret_pb2.RemoveResponse()

    async def _handle_list(self, request: Request) -> None:
        await self._handle(
            request, secret_pb2.ListRequest, secret_pb2.ListResponse, self._call_list
        )

    def _call_list(self, req: secret_pb2.ListRequest) -> secret_pb2.ListResponse:
        secrets = self._adapter.list()
        entries = []
        for key, value in secrets.items():
            if not _may_use(key):
                continue
            entry = secret_pb2.SecretEntry(key=key)
            if value is not None:
                entry.value = value
            entries.append(entry)
        return secret_pb2.ListResponse(found=secret_pb2.ListResult(entries=entries))
