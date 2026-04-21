from __future__ import annotations

import smtplib
from typing import Any

import pytest
from naas_abi_core.services.email.adapters.secondary.SMTPAdapter import SMTPAdapter
from naas_abi_core.services.email.tests.email__secondary_adapter__generic_test import (
    GenericEmailSecondaryAdapterTest,
)


class _FakeSMTPBase:
    instances: list["_FakeSMTPBase"] = []

    def __init__(self, host: str, port: int, timeout: int) -> None:
        self.host = host
        self.port = port
        self.timeout = timeout
        self.did_starttls = False
        self.login_args: tuple[str, str] | None = None
        self.messages: list[Any] = []
        self.__class__.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        return None

    def ehlo(self) -> None:
        return None

    def starttls(self) -> None:
        self.did_starttls = True

    def login(self, username: str, password: str) -> None:
        self.login_args = (username, password)

    def send_message(self, msg) -> None:
        self.messages.append(msg)


class _FakeSMTP(_FakeSMTPBase):
    instances: list[_FakeSMTPBase] = []


class _FakeSMTPSSL(_FakeSMTPBase):
    instances: list[_FakeSMTPBase] = []


class TestSMTPAdapter(GenericEmailSecondaryAdapterTest):
    @pytest.fixture
    def adapter_class(self):
        return SMTPAdapter

    def test_send_email_with_tls(self, monkeypatch) -> None:
        monkeypatch.setattr(smtplib, "SMTP", _FakeSMTP)
        monkeypatch.setattr(smtplib, "SMTP_SSL", _FakeSMTPSSL)

        adapter = SMTPAdapter(
            host="smtp.example.com",
            port=587,
            username="user",
            password="pass",
            use_tls=True,
        )

        adapter.send(
            to_email="alice@example.com",
            subject="Hello",
            text_body="Hello world",
            from_email="noreply@example.com",
            from_name="NEXUS",
        )

        client = _FakeSMTP.instances[-1]
        assert client.host == "smtp.example.com"
        assert client.port == 587
        assert client.did_starttls is True
        assert client.login_args == ("user", "pass")
        assert len(client.messages) == 1
        msg = client.messages[0]
        assert msg["To"] == "alice@example.com"
        assert msg["Subject"] == "Hello"

    def test_send_email_with_ssl(self, monkeypatch) -> None:
        monkeypatch.setattr(smtplib, "SMTP", _FakeSMTP)
        monkeypatch.setattr(smtplib, "SMTP_SSL", _FakeSMTPSSL)

        adapter = SMTPAdapter(
            host="smtp.example.com",
            port=465,
            use_ssl=True,
        )

        adapter.send(
            to_email="bob@example.com",
            subject="Hello",
            text_body="Hello world",
            from_email="noreply@example.com",
        )

        client = _FakeSMTPSSL.instances[-1]
        assert client.host == "smtp.example.com"
        assert client.port == 465
        assert len(client.messages) == 1

    def test_cannot_enable_tls_and_ssl_together(self) -> None:
        with pytest.raises(ValueError):
            SMTPAdapter(
                host="smtp.example.com",
                port=587,
                use_tls=True,
                use_ssl=True,
            )
