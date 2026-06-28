from __future__ import annotations

from typing import Any

import pytest

from naas_abi_core.services.email.adapters.secondary.MicrosoftOutlookAdapter import (
    MicrosoftOutlookAdapter,
)
from naas_abi_core.services.email.EmailPorts import EmailAttachment
from naas_abi_core.services.email.tests.email__secondary_adapter__generic_test import (
    GenericEmailSecondaryAdapterTest,
)


class _FakeGraphClient:
    """Captures Graph API calls without hitting the network."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def get_token(self) -> str:
        return "fake-token"

    def post(self, url: str, payload: dict[str, Any]) -> None:
        self.calls.append((url, payload))


def _make_adapter(client: _FakeGraphClient) -> MicrosoftOutlookAdapter:
    return MicrosoftOutlookAdapter(
        tenant_id="test-tenant",
        client_id="test-client",
        client_secret="test-secret",
        user="sender@example.com",
        client=client,
    )


class TestMicrosoftOutlookAdapter(GenericEmailSecondaryAdapterTest):
    @pytest.fixture
    def adapter_class(self):
        return MicrosoftOutlookAdapter


class TestMicrosoftOutlookAdapterSend:
    def test_send_plain_text_email(self) -> None:
        client = _FakeGraphClient()
        adapter = _make_adapter(client)

        adapter.send(
            to_email="bob@example.com",
            subject="Hello",
            text_body="Hello world",
            from_email="sender@example.com",
        )

        assert len(client.calls) == 1
        url, payload = client.calls[0]
        assert "sender%40example.com/sendMail" in url
        msg = payload["message"]
        assert msg["subject"] == "Hello"
        assert msg["body"] == {"contentType": "Text", "content": "Hello world"}
        assert msg["toRecipients"] == [{"emailAddress": {"address": "bob@example.com"}}]
        assert payload["saveToSentItems"] is True

    def test_send_html_email_prefers_html_body(self) -> None:
        client = _FakeGraphClient()
        adapter = _make_adapter(client)

        adapter.send(
            to_email="bob@example.com",
            subject="Report",
            text_body="plain fallback",
            html_body="<p>html content</p>",
            from_email="sender@example.com",
        )

        _, payload = client.calls[0]
        assert payload["message"]["body"] == {
            "contentType": "HTML",
            "content": "<p>html content</p>",
        }

    def test_send_with_reply_to(self) -> None:
        client = _FakeGraphClient()
        adapter = _make_adapter(client)

        adapter.send(
            to_email="bob@example.com",
            subject="Hello",
            text_body="Hello",
            from_email="sender@example.com",
            reply_to="support@example.com",
        )

        _, payload = client.calls[0]
        assert payload["message"]["replyTo"] == [
            {"emailAddress": {"address": "support@example.com"}}
        ]

    def test_send_with_attachment(self) -> None:
        client = _FakeGraphClient()
        adapter = _make_adapter(client)

        adapter.send(
            to_email="bob@example.com",
            subject="Report",
            text_body="See attached",
            from_email="sender@example.com",
            attachments=[
                EmailAttachment(
                    filename="report.pdf",
                    content=b"%PDF",
                    mime_type="application/pdf",
                )
            ],
        )

        _, payload = client.calls[0]
        att = payload["message"]["attachments"][0]
        assert att["@odata.type"] == "#microsoft.graph.fileAttachment"
        assert att["name"] == "report.pdf"
        assert att["contentType"] == "application/pdf"
        import base64
        assert base64.b64decode(att["contentBytes"]) == b"%PDF"

    def test_send_multiple_recipients(self) -> None:
        client = _FakeGraphClient()
        adapter = _make_adapter(client)

        adapter.send(
            to_emails=["alice@example.com", "bob@example.com"],
            subject="Broadcast",
            text_body="Hello all",
            from_email="sender@example.com",
        )

        _, payload = client.calls[0]
        recipients = [r["emailAddress"]["address"] for r in payload["message"]["toRecipients"]]
        assert recipients == ["alice@example.com", "bob@example.com"]

    def test_from_name_is_accepted_without_error(self) -> None:
        """from_name is silently ignored (Graph API uses Azure AD display name)."""
        client = _FakeGraphClient()
        adapter = _make_adapter(client)

        adapter.send(
            to_email="bob@example.com",
            subject="Hello",
            text_body="Hello",
            from_email="sender@example.com",
            from_name="Ignored Name",
        )

        assert len(client.calls) == 1
        _, payload = client.calls[0]
        assert "from" not in payload["message"]
