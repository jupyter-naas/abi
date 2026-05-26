from __future__ import annotations

import email
from typing import Any

import pytest

boto3 = pytest.importorskip("boto3")

from naas_abi_core.services.email.adapters.secondary.SESAdapter import (  # noqa: E402
    SESAdapter,
)
from naas_abi_core.services.email.tests.email__secondary_adapter__generic_test import (  # noqa: E402
    GenericEmailSecondaryAdapterTest,
)


class _FakeSESClient:
    def __init__(self) -> None:
        self.send_raw_email_calls: list[dict[str, Any]] = []

    def send_raw_email(self, **kwargs: Any) -> dict[str, Any]:
        self.send_raw_email_calls.append(kwargs)
        return {"MessageId": "fake-message-id"}


class _BotoClientFactory:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.client = _FakeSESClient()

    def __call__(self, service_name: str, **kwargs: Any) -> _FakeSESClient:
        self.calls.append({"service_name": service_name, **kwargs})
        return self.client


def _parse_raw_message(call: dict[str, Any]) -> email.message.Message:
    return email.message_from_bytes(call["RawMessage"]["Data"])


class TestSESAdapter(GenericEmailSecondaryAdapterTest):
    @pytest.fixture
    def adapter_class(self):
        return SESAdapter

    def test_send_text_only_email(self, monkeypatch) -> None:
        factory = _BotoClientFactory()
        monkeypatch.setattr(boto3, "client", factory)

        adapter = SESAdapter(region_name="us-east-1")
        adapter.send(
            to_email="alice@example.com",
            subject="Hello",
            text_body="Hello world",
            from_email="noreply@example.com",
        )

        assert factory.calls == [{"service_name": "ses", "region_name": "us-east-1"}]
        assert len(factory.client.send_raw_email_calls) == 1
        call = factory.client.send_raw_email_calls[0]
        assert call["Source"] == "noreply@example.com"
        assert call["Destinations"] == ["alice@example.com"]

        msg = _parse_raw_message(call)
        assert msg["To"] == "alice@example.com"
        assert msg["Subject"] == "Hello"
        assert msg["From"] == "noreply@example.com"
        assert msg.get("Reply-To") is None
        assert "Hello world" in msg.get_payload(decode=False) if not msg.is_multipart() else any(
            "Hello world" in part.get_payload(decode=True).decode()
            for part in msg.walk()
            if part.get_content_type() == "text/plain"
        )

    def test_send_html_email_with_from_name_and_reply_to(self, monkeypatch) -> None:
        factory = _BotoClientFactory()
        monkeypatch.setattr(boto3, "client", factory)

        adapter = SESAdapter(region_name="eu-west-1")
        adapter.send(
            to_email="bob@example.com",
            subject="Hi Bob",
            text_body="plain",
            html_body="<p>html</p>",
            from_email="noreply@example.com",
            from_name="NEXUS",
            reply_to="support@example.com",
        )

        call = factory.client.send_raw_email_calls[-1]
        assert call["Source"] == "noreply@example.com"
        assert call["Destinations"] == ["bob@example.com"]

        msg = _parse_raw_message(call)
        assert msg["From"] == "NEXUS <noreply@example.com>"
        assert msg["Reply-To"] == "support@example.com"
        assert msg["Subject"] == "Hi Bob"
        assert msg.is_multipart()
        parts = {part.get_content_type(): part for part in msg.walk()}
        assert "text/plain" in parts
        assert "text/html" in parts
        assert "plain" in parts["text/plain"].get_payload(decode=True).decode()
        assert "<p>html</p>" in parts["text/html"].get_payload(decode=True).decode()

    def test_explicit_credentials_passed_to_boto_client(self, monkeypatch) -> None:
        factory = _BotoClientFactory()
        monkeypatch.setattr(boto3, "client", factory)

        adapter = SESAdapter(
            region_name="us-east-1",
            aws_access_key_id="AKIA...",
            aws_secret_access_key="secret",
            aws_session_token="token",
        )
        adapter.send(
            to_email="alice@example.com",
            subject="s",
            text_body="b",
            from_email="noreply@example.com",
        )

        assert factory.calls == [
            {
                "service_name": "ses",
                "region_name": "us-east-1",
                "aws_access_key_id": "AKIA...",
                "aws_secret_access_key": "secret",
                "aws_session_token": "token",
            }
        ]

    def test_injected_client_is_used_directly(self) -> None:
        client = _FakeSESClient()
        adapter = SESAdapter(client=client)

        adapter.send(
            to_email="alice@example.com",
            subject="s",
            text_body="b",
            from_email="noreply@example.com",
        )

        assert len(client.send_raw_email_calls) == 1
