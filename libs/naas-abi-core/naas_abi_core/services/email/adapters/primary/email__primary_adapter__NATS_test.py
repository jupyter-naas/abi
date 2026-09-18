"""Unit tests for EmailPrimaryAdapterNATS's auth/dispatch/error-mapping.

None of these need a real NATS server: each handler is invoked directly
against a minimal fake ``Request`` that records whatever gets passed to
``respond``, matching the "test the handler logic directly" option called
out for this adapter.
"""

import asyncio

from naas_abi_core.engine.nats_auth import issue_service_token
from naas_abi_core.proto.email.v1 import email_pb2
from naas_abi_core.services.email.adapters.primary.email__primary_adapter__NATS import (
    AUTH_HEADER,
    EmailPrimaryAdapterNATS,
)
from naas_abi_core.services.email.EmailPorts import EmailAttachment, IEmailAdapter

SECRET = "test-shared-secret"


class _FakeRequest:
    """Stands in for nats.micro.request.Request: same ``.data``/``.headers``
    surface, and ``respond`` just records the payload instead of publishing
    it anywhere."""

    def __init__(
        self,
        data: bytes,
        headers: dict[str, str] | None = None,
        subject: str = "abi.svc.email.v1.send",
    ) -> None:
        self.data = data
        self.headers = headers
        self.subject = subject
        self.responses: list[bytes] = []

    async def respond(
        self, data: bytes = b"", headers: dict[str, str] | None = None
    ) -> None:
        self.responses.append(data)


class _StubAdapter(IEmailAdapter):
    """Minimal in-memory IEmailAdapter for driving the handler."""

    def __init__(self) -> None:
        self.sent: list[dict] = []

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
    ) -> None:
        self.sent.append(
            {
                "to_email": to_email,
                "subject": subject,
                "text_body": text_body,
                "html_body": html_body,
                "from_email": from_email,
                "from_name": from_name,
                "reply_to": reply_to,
                "attachments": attachments,
                "to_emails": to_emails,
                "cc_emails": cc_emails,
            }
        )


def _valid_token() -> str:
    return issue_service_token("api", SECRET)


def _send_request(
    *,
    html_body: str | None = None,
    from_name: str | None = None,
    reply_to: str | None = None,
) -> bytes:
    return email_pb2.SendRequest(
        to_email="alice@example.com",
        subject="Hello",
        text_body="Hello world",
        from_email="noreply@example.com",
        html_body=html_body,
        from_name=from_name,
        reply_to=reply_to,
    ).SerializeToString()


# ---------------------------------------------------------------------------
# Auth.
# ---------------------------------------------------------------------------


def test_missing_token_returns_unauthenticated():
    adapter = EmailPrimaryAdapterNATS(_StubAdapter(), SECRET)
    request = _FakeRequest(data=_send_request(), headers=None)

    asyncio.run(adapter._handle_send(request))

    response = email_pb2.SendResponse()
    response.ParseFromString(request.responses[0])
    assert response.HasField("error")
    assert response.error.code == "UNAUTHENTICATED"
    assert response.error.retryable is False


def test_empty_token_header_returns_unauthenticated():
    adapter = EmailPrimaryAdapterNATS(_StubAdapter(), SECRET)
    request = _FakeRequest(data=_send_request(), headers={AUTH_HEADER: ""})

    asyncio.run(adapter._handle_send(request))

    response = email_pb2.SendResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.code == "UNAUTHENTICATED"


def test_malformed_token_returns_unauthenticated():
    adapter = EmailPrimaryAdapterNATS(_StubAdapter(), SECRET)
    request = _FakeRequest(data=_send_request(), headers={AUTH_HEADER: "not-a-jwt"})

    asyncio.run(adapter._handle_send(request))

    response = email_pb2.SendResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.code == "UNAUTHENTICATED"


def test_token_signed_with_wrong_secret_returns_unauthenticated():
    adapter = EmailPrimaryAdapterNATS(_StubAdapter(), SECRET)
    wrong_secret_token = issue_service_token("api", "a-different-secret")
    request = _FakeRequest(
        data=_send_request(), headers={AUTH_HEADER: wrong_secret_token}
    )

    asyncio.run(adapter._handle_send(request))

    response = email_pb2.SendResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.code == "UNAUTHENTICATED"


# ---------------------------------------------------------------------------
# Happy path.
# ---------------------------------------------------------------------


def test_successful_send_returns_no_error_and_forwards_fields():
    stub = _StubAdapter()
    adapter = EmailPrimaryAdapterNATS(stub, SECRET)
    request = _FakeRequest(
        data=_send_request(
            html_body="<p>hi</p>",
            from_name="NEXUS",
            reply_to="support@example.com",
        ),
        headers={AUTH_HEADER: _valid_token()},
    )

    asyncio.run(adapter._handle_send(request))

    response = email_pb2.SendResponse()
    response.ParseFromString(request.responses[0])
    assert not response.HasField("error")
    assert len(stub.sent) == 1
    call = stub.sent[0]
    assert call["to_email"] == "alice@example.com"
    assert call["subject"] == "Hello"
    assert call["text_body"] == "Hello world"
    assert call["html_body"] == "<p>hi</p>"
    assert call["from_email"] == "noreply@example.com"
    assert call["from_name"] == "NEXUS"
    assert call["reply_to"] == "support@example.com"


def test_unset_optional_fields_are_forwarded_as_none():
    stub = _StubAdapter()
    adapter = EmailPrimaryAdapterNATS(stub, SECRET)
    request = _FakeRequest(
        data=email_pb2.SendRequest(
            subject="Hello",
            text_body="Body",
            from_email="noreply@example.com",
        ).SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
    )

    asyncio.run(adapter._handle_send(request))

    call = stub.sent[0]
    assert call["to_email"] is None
    assert call["html_body"] is None
    assert call["from_name"] is None
    assert call["reply_to"] is None
    assert call["attachments"] is None
    assert call["to_emails"] is None
    assert call["cc_emails"] is None


def test_to_emails_and_cc_emails_and_attachments_round_trip():
    stub = _StubAdapter()
    adapter = EmailPrimaryAdapterNATS(stub, SECRET)
    request = _FakeRequest(
        data=email_pb2.SendRequest(
            subject="Hello",
            text_body="Body",
            from_email="noreply@example.com",
            to_emails=["a@example.com", "b@example.com"],
            cc_emails=["c@example.com"],
            attachments=[
                email_pb2.EmailAttachment(
                    filename="report.pdf",
                    content=b"%PDF-1.4",
                    mime_type="application/pdf",
                ),
                email_pb2.EmailAttachment(
                    filename="logo.png",
                    content=b"\x89PNG",
                    mime_type="image/png",
                    content_id="logo",
                    is_inline=True,
                ),
            ],
        ).SerializeToString(),
        headers={AUTH_HEADER: _valid_token()},
    )

    asyncio.run(adapter._handle_send(request))

    call = stub.sent[0]
    assert call["to_emails"] == ["a@example.com", "b@example.com"]
    assert call["cc_emails"] == ["c@example.com"]
    attachments = call["attachments"]
    assert attachments is not None
    assert len(attachments) == 2
    assert attachments[0] == EmailAttachment(
        filename="report.pdf", content=b"%PDF-1.4", mime_type="application/pdf"
    )
    assert attachments[1] == EmailAttachment(
        filename="logo.png",
        content=b"\x89PNG",
        mime_type="image/png",
        content_id="logo",
        is_inline=True,
    )


# ---------------------------------------------------------------------------
# Generic exception -> INTERNAL (no domain exceptions are declared in
# EmailPorts.py, so this is the only error-mapping path besides auth).
# ---------------------------------------------------------------------------


def test_unexpected_exception_maps_to_internal_and_does_not_leak_message():
    class _BoomAdapter(_StubAdapter):
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
        ) -> None:
            raise RuntimeError("some sensitive internal detail")

    adapter = EmailPrimaryAdapterNATS(_BoomAdapter(), SECRET)
    request = _FakeRequest(data=_send_request(), headers={AUTH_HEADER: _valid_token()})

    asyncio.run(adapter._handle_send(request))

    response = email_pb2.SendResponse()
    response.ParseFromString(request.responses[0])
    assert response.error.code == "INTERNAL"
    assert response.error.retryable is True
    assert "sensitive internal detail" not in response.error.message


# ---------------------------------------------------------------------------
# Lifecycle no-ops.
# ---------------------------------------------------------------------------


def test_stop_without_start_is_a_noop():
    adapter = EmailPrimaryAdapterNATS(_StubAdapter(), SECRET)
    asyncio.run(adapter.stop())  # must not raise
