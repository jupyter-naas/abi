"""NATS RPC client adapter for the email kernel domain.

Implements ``IEmailAdapter`` by calling out to a remote
``EmailPrimaryAdapterNATS`` over NATS request/reply -- see
``naas_abi_core/proto/email/v1/email.proto`` for the wire contract and
``naas_abi_core/proto/README.md`` for why it lives there.

Shared connection, token, timeout, and reply handling live in
``naas_abi_core.engine.nats_rpc.NatsRPCClient``. Calls are never replayed
by the transport after failure; a timeout may hide a completed operation.

Stage 1 auth model (see ``naas_abi_core.engine.nats_auth``): a JWT asserting
``service_identity`` is issued once and attached on the ``Nats-Auth-Token``
header of every request, reissued only when it is close to expiry rather
than on every call. ``EmailPrimaryAdapterNATS`` must read the token from
that exact header -- both sides read ``AUTH_HEADER`` from
``email_nats_contract``, a neutral module neither adapter owns, so this
file never has to import from the primary adapter's module (or vice versa)
just to agree on a header name.
"""

from __future__ import annotations

from naas_abi_core.engine.nats_rpc import NatsRPCClient
from naas_abi_core.proto.common.v1 import common_pb2
from naas_abi_core.proto.email.v1 import email_pb2
from naas_abi_core.services.email.adapters.email_nats_contract import (
    AUTH_HEADER,
    SUBJECT_PREFIX,
)
from naas_abi_core.services.email.EmailPorts import (
    EmailAttachment,
    IEmailAdapter,
    SentEmail,
    SentEmailNotFound,
    SentEmailsNotKept,
    SentEmailSummary,
)


def _attachment_to_pb(attachment: EmailAttachment) -> email_pb2.EmailAttachment:
    pb = email_pb2.EmailAttachment(
        filename=attachment.filename,
        content=attachment.content,
        mime_type=attachment.mime_type,
        is_inline=attachment.is_inline,
    )
    if attachment.content_id is not None:
        pb.content_id = attachment.content_id
    return pb


def _to_list(value: list[str] | str | None) -> list[str]:
    """Normalize the port's ``list[str] | str | None`` recipient shape into
    the plain list the wire's ``repeated string`` field carries.

    A bare string becomes a one-element list; ``None`` becomes an empty
    list. This does NOT split comma-separated addresses -- that stays the
    server side's job (``EmailPorts.resolve_recipients``, invoked inside
    ``EmailService.send``/the wrapped adapter), same as it is today
    in-process.
    """
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    return list(value)


def _pb_to_summary(pb: email_pb2.SentEmailSummary) -> SentEmailSummary:
    return SentEmailSummary(
        message_id=pb.message_id,
        sent_at=pb.sent_at,
        size=pb.size,
        subject=pb.subject,
        to=pb.to,
        sender=pb.sender,
    )


def _raise_for_error(error: common_pb2.CallError) -> None:
    """Raise the exception matching ``error.code``.

    Must stay exactly symmetric with how ``EmailPrimaryAdapterNATS`` encodes
    errors: ``SENT_EMAILS_NOT_KEPT`` and ``SENT_EMAIL_NOT_FOUND`` map back to
    their ``EmailPorts`` exceptions; every other failure the server can report
    -- including its own catch-all -- falls through to ``RuntimeError``.
    """
    if error.code == "SENT_EMAILS_NOT_KEPT":
        raise SentEmailsNotKept(error.message)
    if error.code == "SENT_EMAIL_NOT_FOUND":
        raise SentEmailNotFound(error.message)
    raise RuntimeError(f"email NATS RPC failed ({error.code}): {error.message}")


class EmailSecondaryAdapterNATSClient(NatsRPCClient, IEmailAdapter):
    """Calls a remote ``EmailPrimaryAdapterNATS`` over NATS RPC."""

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
    # IEmailAdapter.
    # ------------------------------------------------------------------

    def send(
        self,
        *,
        to_email: str | None = None,
        subject: str,
        text_body: str,
        html_body: str | None = None,
        from_email: str,
        from_name: str | None = None,
        reply_to: str | None = None,
        attachments: list[EmailAttachment] | None = None,
        to_emails: list[str] | str | None = None,
        cc_emails: list[str] | str | None = None,
    ) -> str | None:
        request = email_pb2.SendRequest(
            context=self._context(),
            subject=subject,
            text_body=text_body,
            from_email=from_email,
            attachments=[_attachment_to_pb(a) for a in attachments or []],
            to_emails=_to_list(to_emails),
            cc_emails=_to_list(cc_emails),
        )
        if to_email is not None:
            request.to_email = to_email
        if html_body is not None:
            request.html_body = html_body
        if from_name is not None:
            request.from_name = from_name
        if reply_to is not None:
            request.reply_to = reply_to

        response = self._call(f"{SUBJECT_PREFIX}.send", request, email_pb2.SendResponse)
        if response.HasField("error"):
            _raise_for_error(response.error)
        return response.message_id if response.HasField("message_id") else None

    def list_sent(
        self, *, limit: int = 100, before: str | None = None
    ) -> list[SentEmailSummary]:
        request = email_pb2.ListSentRequest(context=self._context(), limit=limit)
        if before is not None:
            request.before = before
        response = self._call(
            f"{SUBJECT_PREFIX}.list_sent", request, email_pb2.ListSentResponse
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        return [_pb_to_summary(pb) for pb in response.messages.messages]

    def get_sent(self, message_id: str) -> SentEmail:
        request = email_pb2.GetSentRequest(
            context=self._context(), message_id=message_id
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.get_sent", request, email_pb2.GetSentResponse
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
        return SentEmail(
            summary=_pb_to_summary(response.message.summary), raw=response.message.raw
        )

    def delete_sent(self, message_id: str) -> None:
        request = email_pb2.DeleteSentRequest(
            context=self._context(), message_id=message_id
        )
        response = self._call(
            f"{SUBJECT_PREFIX}.delete_sent", request, email_pb2.DeleteSentResponse
        )
        if response.HasField("error"):
            _raise_for_error(response.error)
