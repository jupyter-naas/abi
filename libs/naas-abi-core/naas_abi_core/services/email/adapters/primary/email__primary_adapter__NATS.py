"""NATS RPC primary adapter for the email kernel domain.

Exposes a real ``IEmailAdapter`` (or, in practice, the ``EmailService``
domain wrapping one) as a NATS micro-service (see
``naas_abi_core/proto/email/v1/email.proto`` for the wire contract and
``naas_abi_core/proto/README.md`` for why it lives there). This is the
server side; the matching client is ``EmailSecondaryAdapterNATSClient``.

Stage 1 auth model (see ``naas_abi_core.engine.nats_auth``): one shared
secret, one claim -- which known first-party process holds the token. Every
incoming request must carry a valid token in the ``Nats-Auth-Token`` header
(``AUTH_HEADER``, imported from ``email_nats_contract`` below -- that's a
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
from naas_abi_core.proto.common.v1 import common_pb2
from naas_abi_core.proto.email.v1 import email_pb2
from naas_abi_core.services.email.adapters.email_nats_contract import (
    AUTH_HEADER,
    SERVICE_NAME,
    SERVICE_VERSION,
    SUBJECT_PREFIX,
)
from naas_abi_core.services.email.EmailPorts import EmailAttachment, IEmailAdapter
from naas_abi_core.services.email.EmailService import EmailService
from nats.micro.request import Request
from nats.micro.service import Service

__all__ = [
    "AUTH_HEADER",
    "SERVICE_NAME",
    "SERVICE_VERSION",
    "SUBJECT_PREFIX",
    "EmailPrimaryAdapterNATS",
]

_RequestT = TypeVar("_RequestT", bound=Message)
_ResponseT = TypeVar("_ResponseT", bound=Message)


def _pb_to_attachments(
    pb_attachments: list[email_pb2.EmailAttachment],
) -> list[EmailAttachment] | None:
    """Convert the wire attachments into the port's ``EmailAttachment`` list.

    An empty repeated field is treated the same as "no attachments" (``None``)
    -- see the ``.proto`` file's comment: ``EmailMessageBuilder.build_email_message``
    already treats ``attachments=None`` and ``attachments=[]`` identically
    (``for attachment in attachments or []``), so no extra presence tracking
    is needed here.
    """
    if not pb_attachments:
        return None
    return [
        EmailAttachment(
            filename=pb.filename,
            content=pb.content,
            mime_type=pb.mime_type,
            content_id=pb.content_id if pb.HasField("content_id") else None,
            is_inline=pb.is_inline,
        )
        for pb in pb_attachments
    ]


class EmailPrimaryAdapterNATS:
    """Serves email over NATS RPC (request/reply).

    Wraps a real adapter *or* the domain service and registers one NATS
    micro-service endpoint for ``send``, the only non-streaming method on
    ``IEmailAdapter``. The endpoint authenticates the caller via
    ``Nats-Auth-Token`` before doing anything else, then decodes the
    Protobuf request, calls straight through to the wrapped object, and
    encodes a Protobuf response. Errors -- auth failures, anything
    unexpected -- are always reported as a normal response carrying a
    populated ``CallError``, never as a crashed handler or a raw NATS-level
    error.

    Accepts either an ``IEmailAdapter`` (a bare secondary adapter, e.g. in
    tests) or an ``EmailService`` (the real engine-loaded domain service) --
    deliberately, not for convenience: wrapping the raw adapter instead of
    the domain service would silently skip ``EmailService``'s event
    publishing (``EmailSent``/``EmailError``) for every remote caller, which
    would only diverge from in-process behaviour, not match it.
    ``EngineNATSLoader`` always passes the domain service.
    """

    def __init__(
        self,
        adapter: IEmailAdapter | EmailService,
        jwt_secret: str,
    ) -> None:
        self._adapter = adapter
        self._jwt_secret = jwt_secret
        self._dispatch = DomainRPCDispatcher(SERVICE_NAME)
        self._service: Service | None = None

    async def start(self, nc: nats.NATS) -> None:
        """Register the ``email`` NATS service on ``nc``.

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
            description="ABI kernel email domain, exposed over NATS RPC (v1).",
        )
        await service.add_endpoint(
            name="send",
            subject=f"{SUBJECT_PREFIX}.send",
            handler=self._handle_send,
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
        except Exception:  # noqa: BLE001 - a handler must never crash the service
            logger.opt(exception=True).error(
                f"EmailPrimaryAdapterNATS: unexpected error handling {request.subject!r}"
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
    # Endpoint handlers -- one per non-streaming IEmailAdapter method.
    # ------------------------------------------------------------------

    async def _handle_send(self, request: Request) -> None:
        await self._handle(
            request,
            email_pb2.SendRequest,
            email_pb2.SendResponse,
            self._call_send,
        )

    def _call_send(self, req: email_pb2.SendRequest) -> email_pb2.SendResponse:
        self._adapter.send(
            to_email=req.to_email if req.HasField("to_email") else None,
            subject=req.subject,
            text_body=req.text_body,
            html_body=req.html_body if req.HasField("html_body") else None,
            from_email=req.from_email,
            from_name=req.from_name if req.HasField("from_name") else None,
            reply_to=req.reply_to if req.HasField("reply_to") else None,
            attachments=_pb_to_attachments(list(req.attachments)),
            to_emails=list(req.to_emails) if req.to_emails else None,
            cc_emails=list(req.cc_emails) if req.cc_emails else None,
        )
        return email_pb2.SendResponse()
