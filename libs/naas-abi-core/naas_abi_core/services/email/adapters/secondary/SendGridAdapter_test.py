from __future__ import annotations

from typing import Any

import pytest

from naas_abi_core.services.email.adapters.secondary.SendGridAdapter import (
    SendGridAdapter,
)
from naas_abi_core.services.email.EmailPorts import EmailAttachment
from naas_abi_core.services.email.tests.email__secondary_adapter__generic_test import (
    GenericEmailSecondaryAdapterTest,
)


class _FakeSendGridClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def post(self, endpoint: str, payload: dict[str, Any]) -> None:
        self.calls.append((endpoint, payload))


class TestSendGridAdapter(GenericEmailSecondaryAdapterTest):
    @pytest.fixture
    def adapter_class(self):
        return SendGridAdapter

    def test_send_html_email_with_from_name_and_attachments(self) -> None:
        client = _FakeSendGridClient()
        adapter = SendGridAdapter(api_key="test-key", client=client)

        adapter.send(
            to_email="bob@example.com",
            subject="Report",
            text_body="plain",
            html_body="<p>html</p>",
            from_email="noreply@example.com",
            from_name="AXI Reports",
            reply_to="support@example.com",
            attachments=[
                EmailAttachment(
                    filename="report.html",
                    content=b"<html></html>",
                    mime_type="text/html",
                )
            ],
        )

        assert len(client.calls) == 1
        endpoint, payload = client.calls[0]
        assert endpoint == "/mail/send"
        assert payload["from"] == {
            "email": "noreply@example.com",
            "name": "AXI Reports",
        }
        assert payload["reply_to"] == {"email": "support@example.com"}
        assert payload["personalizations"] == [
            {"to": [{"email": "bob@example.com"}]}
        ]
        assert payload["subject"] == "Report"
        assert payload["content"] == [
            {"type": "text/plain", "value": "plain"},
            {"type": "text/html", "value": "<p>html</p>"},
        ]
        assert payload["attachments"][0]["filename"] == "report.html"
        assert payload["attachments"][0]["type"] == "text/html"
        assert payload["attachments"][0]["disposition"] == "attachment"

    def test_send_text_only_email(self) -> None:
        client = _FakeSendGridClient()
        adapter = SendGridAdapter(api_key="test-key", client=client)

        adapter.send(
            to_email="alice@example.com",
            subject="Hello",
            text_body="Hello world",
            from_email="noreply@example.com",
        )

        _, payload = client.calls[0]
        assert payload["content"] == [{"type": "text/plain", "value": "Hello world"}]

    def test_http_error_is_wrapped(self, monkeypatch) -> None:
        requests = pytest.importorskip("requests")

        class _Response:
            status_code = 403
            reason = "Forbidden"
            text = "invalid api key"

        def _raise_for_status(*args, **kwargs):
            return _Response()

        def _post(*args, **kwargs):
            return _Response()

        monkeypatch.setattr(requests, "post", _post)
        adapter = SendGridAdapter(api_key="bad-key")

        with pytest.raises(RuntimeError, match="SendGrid API request failed"):
            adapter.send(
                to_email="alice@example.com",
                subject="Hello",
                text_body="Hello world",
                from_email="noreply@example.com",
            )
