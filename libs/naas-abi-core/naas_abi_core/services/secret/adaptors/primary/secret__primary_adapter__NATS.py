"""NATS RPC primary adapter for the secret kernel domain.

Exposes a real ``ISecretAdapter`` (or, for the real deployed case, the
``Secret`` domain facade fanning out over several of them) as a NATS
micro-service (see ``naas_abi_core/proto/secret/v1/secret.proto`` for the
wire contract and ``naas_abi_core/proto/README.md`` for why it lives
there). This is the server side; the matching client is
``SecretSecondaryAdapterNATSClient``.

Rights follow the caller's verified service identity
(``naas_abi_core.engine.nats_auth``), never the request. The engine's own
processes (``FIRST_PARTY_IDENTITIES``) hold the project secret and keep full
access. An SDK module holds nothing by default: it reads, lists, writes and
removes only the secret names an operator granted it (``nats.secret.modules``,
docs/adr/20261024_secret-service-closed-to-sdk-modules.md). A name it may not
read is answered as not found and left out of ``list``, so nothing says which
secrets exist; a write it may not make is PERMISSION_DENIED whether or not the
name exists. A value a module writes is opaque, never interpolated: one holding ``$``, a
quote, a backslash or a line break is refused (INVALID_ARGUMENT), because the backends
parse stored text and would expand it, reading another secret or adding a key.
"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping, Sequence
from typing import TypeVar

import nats
import nats.micro
from google.protobuf.message import DecodeError, Message
from naas_abi_core import logger
from naas_abi_core.engine.nats_auth import (
    FIRST_PARTY_IDENTITIES,
    InvalidServiceTokenError,
    verify_service_token,
)
from naas_abi_core.engine.nats_dispatch import DomainRPCDispatcher
from naas_abi_core.engine.nats_rpc import (
    RequestPayloadError,
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

# What the backends read as syntax when they parse stored text back: dotenv expands
# ``${NAME}`` (even inside quotes) from the file and the environment, and quotes,
# backslashes and line breaks end or extend a value. A value a module writes is
# opaque, so none of it is accepted.
_SYNTAX = re.compile(r"[$'\"\\\n\r]")

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

    ``module_read`` / ``module_write``: per SDK module identity, the secret
    names it may read (``get``, ``list``) and write (``set``, ``remove``).
    Both are empty by default, and first-party identities cannot be keys:
    those processes are trusted already.
    """

    def __init__(
        self,
        adapter: ISecretAdapter | Secret,
        jwt_secret: str,
        *,
        module_read: Mapping[str, Sequence[str]] | None = None,
        module_write: Mapping[str, Sequence[str]] | None = None,
    ) -> None:
        self._adapter = adapter
        self._jwt_secret = jwt_secret
        self._module_read = self._grants("module_read", module_read)
        self._module_write = self._grants("module_write", module_write)
        self._dispatch = DomainRPCDispatcher(SERVICE_NAME)
        self._service: TracedService | None = None

    @staticmethod
    def _grants(
        label: str, grants: Mapping[str, Sequence[str]] | None
    ) -> dict[str, frozenset[str]]:
        for identity in grants or {}:
            if identity in FIRST_PARTY_IDENTITIES:
                raise ValueError(
                    f"{label} names SDK module identities, not the first-party "
                    f"{identity!r}: the engine's own processes are trusted already"
                )
        return {
            identity: frozenset(names) for identity, names in (grants or {}).items()
        }

    def _may(
        self, grants: Mapping[str, frozenset[str]], identity: str, key: str
    ) -> bool:
        if identity in FIRST_PARTY_IDENTITIES:
            return True
        return key in grants.get(identity, ())

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
        call: Callable[[_RequestT, str], _ResponseT],
    ) -> None:
        identity = self._authenticate(request)
        if identity is None:
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
            response = await self._dispatch.call(
                lambda req: call(req, identity), parsed_request
            )
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

        await respond_protobuf(request, response, response_cls)

    def _authenticate(self, request: Request) -> str | None:
        """The caller's verified identity, or ``None`` for a missing or bad token."""
        headers = request.headers or {}
        token = headers.get(AUTH_HEADER)
        if not token:
            return None
        try:
            return verify_service_token(token, self._jwt_secret)
        except InvalidServiceTokenError:
            return None

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

    @staticmethod
    def _denied() -> common_pb2.CallError:
        # The same answer for every name, so it never says which ones exist.
        return common_pb2.CallError(
            code="PERMISSION_DENIED",
            message="This caller may not write that secret",
            retryable=False,
        )

    # ------------------------------------------------------------------
    # Endpoint handlers -- one per ISecretAdapter method.
    # ------------------------------------------------------------------

    async def _handle_get(self, request: Request) -> None:
        await self._handle(
            request, secret_pb2.GetRequest, secret_pb2.GetResponse, self._call_get
        )

    def _call_get(
        self, req: secret_pb2.GetRequest, identity: str
    ) -> secret_pb2.GetResponse:
        # No `default` argument here -- see secret.proto's header comment:
        # the client applies its caller's default locally when unset.
        # A name the caller may not read is not looked up: it is not found.
        value = (
            self._adapter.get(req.key, None)
            if self._may(self._module_read, identity, req.key)
            else None
        )
        result = secret_pb2.GetResult()
        if value is not None:
            result.value = str(value)
        return secret_pb2.GetResponse(found=result)

    async def _handle_set(self, request: Request) -> None:
        await self._handle(
            request, secret_pb2.SetRequest, secret_pb2.SetResponse, self._call_set
        )

    def _call_set(
        self, req: secret_pb2.SetRequest, identity: str
    ) -> secret_pb2.SetResponse:
        if not self._may(self._module_write, identity, req.key):
            return secret_pb2.SetResponse(error=self._denied())
        if identity not in FIRST_PARTY_IDENTITIES and _SYNTAX.search(req.value):
            return secret_pb2.SetResponse(
                error=common_pb2.CallError(
                    code="INVALID_ARGUMENT",
                    message=(
                        "A secret value written by a module may not contain "
                        "$, quotes, backslashes or line breaks"
                    ),
                    retryable=False,
                )
            )
        self._adapter.set(req.key, req.value)
        return secret_pb2.SetResponse()

    async def _handle_remove(self, request: Request) -> None:
        await self._handle(
            request,
            secret_pb2.RemoveRequest,
            secret_pb2.RemoveResponse,
            self._call_remove,
        )

    def _call_remove(
        self, req: secret_pb2.RemoveRequest, identity: str
    ) -> secret_pb2.RemoveResponse:
        if not self._may(self._module_write, identity, req.key):
            return secret_pb2.RemoveResponse(error=self._denied())
        self._adapter.remove(req.key)
        return secret_pb2.RemoveResponse()

    async def _handle_list(self, request: Request) -> None:
        await self._handle(
            request, secret_pb2.ListRequest, secret_pb2.ListResponse, self._call_list
        )

    def _call_list(
        self, req: secret_pb2.ListRequest, identity: str
    ) -> secret_pb2.ListResponse:
        secrets = self._adapter.list()
        entries = []
        for key, value in secrets.items():
            if not self._may(self._module_read, identity, key):
                continue
            entry = secret_pb2.SecretEntry(key=key)
            if value is not None:
                entry.value = value
            entries.append(entry)
        return secret_pb2.ListResponse(found=secret_pb2.ListResult(entries=entries))
