"""A send that names no sender leaves from the adapter's configured default.

The built-in identity provider sends its sign-in codes with ``from_email=""``
(issue #1643): the deployment's own mailbox is the one its email adapter is
configured with, so every adapter takes a default sender and uses it then. With
no sender anywhere, the send fails with ``EmailDeliveryError`` before reaching
the provider, instead of a relay's refusal.
"""

from __future__ import annotations

import smtplib
from email import message_from_bytes
from pathlib import Path
from typing import Any, Self

import pytest
from naas_abi_core.engine.engine_configuration.EngineConfiguration_EmailService import (
    EmailAdapterConfiguration,
)
from naas_abi_core.services.email.adapters.secondary.FilesystemAdapter import (
    FilesystemAdapter,
)
from naas_abi_core.services.email.adapters.secondary.MicrosoftOutlookAdapter import (
    MicrosoftOutlookAdapter,
)
from naas_abi_core.services.email.adapters.secondary.SendGridAdapter import (
    SendGridAdapter,
)
from naas_abi_core.services.email.adapters.secondary.SESAdapter import SESAdapter
from naas_abi_core.services.email.adapters.secondary.SMTPAdapter import SMTPAdapter
from naas_abi_core.services.email.EmailPorts import (
    EmailDeliveryError,
    resolve_sender,
)

MAIL: dict[str, Any] = {
    "to_email": "alice@example.com",
    "subject": "Your code",
    "text_body": "12345678",
}


class TestResolveSender:
    def test_the_send_s_own_sender_wins(self) -> None:
        assert resolve_sender("a@example.com", "d@example.com") == "a@example.com"

    def test_an_empty_sender_falls_back_to_the_default(self) -> None:
        assert resolve_sender("", "d@example.com") == "d@example.com"
        assert resolve_sender("  ", "d@example.com") == "d@example.com"
        assert resolve_sender(None, "d@example.com") == "d@example.com"

    def test_no_sender_anywhere_is_an_email_delivery_error(self) -> None:
        with pytest.raises(EmailDeliveryError, match="No sender"):
            resolve_sender("", None)
        with pytest.raises(EmailDeliveryError, match="No sender"):
            resolve_sender("", "")


# --- Provider adapters -------------------------------------------------------


class _FakeSMTP:
    instances: list[_FakeSMTP] = []
    refuse: Exception | None = None

    def __init__(self, host: str, port: int, timeout: int) -> None:
        self.messages: list[Any] = []
        _FakeSMTP.instances.append(self)

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def ehlo(self) -> None:
        return None

    def send_message(self, msg: Any) -> None:
        if _FakeSMTP.refuse is not None:
            raise _FakeSMTP.refuse
        self.messages.append(msg)


@pytest.fixture
def fake_smtp(monkeypatch: pytest.MonkeyPatch) -> type[_FakeSMTP]:
    _FakeSMTP.instances = []
    _FakeSMTP.refuse = None
    monkeypatch.setattr(smtplib, "SMTP", _FakeSMTP)
    return _FakeSMTP


class TestSMTPAdapter:
    def test_an_empty_sender_uses_the_configured_one(self, fake_smtp) -> None:
        SMTPAdapter(host="relay", port=25, from_email="team@example.com").send(
            **MAIL, from_email=""
        )
        assert fake_smtp.instances[0].messages[0]["From"] == "team@example.com"

    def test_the_send_s_sender_wins_over_the_default(self, fake_smtp) -> None:
        SMTPAdapter(host="relay", port=25, from_email="team@example.com").send(
            **MAIL, from_email="other@example.com"
        )
        assert fake_smtp.instances[0].messages[0]["From"] == "other@example.com"

    def test_no_sender_fails_before_connecting(self, fake_smtp) -> None:
        with pytest.raises(EmailDeliveryError, match="No sender"):
            SMTPAdapter(host="relay", port=25).send(**MAIL, from_email="")
        assert fake_smtp.instances == []

    def test_a_refusal_names_the_relay_s_answer(self, fake_smtp) -> None:
        fake_smtp.refuse = smtplib.SMTPSenderRefused(
            553, b"sender not allowed", "x@example.com"
        )
        with pytest.raises(EmailDeliveryError, match="sender not allowed"):
            SMTPAdapter(host="relay", port=25).send(**MAIL, from_email="x@example.com")


class _FakeSES:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def send_raw_email(self, **kwargs: Any) -> None:
        self.calls.append(kwargs)


class TestSESAdapter:
    def test_an_empty_sender_uses_the_configured_one(self) -> None:
        client = _FakeSES()
        SESAdapter(from_email="team@example.com", client=client).send(
            **MAIL, from_email=""
        )
        call = client.calls[0]
        assert call["Source"] == "team@example.com"
        msg = message_from_bytes(call["RawMessage"]["Data"])
        assert msg["From"] == "team@example.com"

    def test_no_sender_fails_before_calling_ses(self) -> None:
        client = _FakeSES()
        with pytest.raises(EmailDeliveryError, match="No sender"):
            SESAdapter(client=client).send(**MAIL, from_email="")
        assert client.calls == []


class _FakeHTTP:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def post(self, url: str, payload: dict[str, Any]) -> None:
        self.calls.append((url, payload))

    def get_token(self) -> str:
        return "token"


class TestSendGridAdapter:
    def test_an_empty_sender_uses_the_configured_one(self) -> None:
        client = _FakeHTTP()
        SendGridAdapter(api_key="k", from_email="team@example.com", client=client).send(
            **MAIL, from_email=""
        )
        assert client.calls[0][1]["from"] == {"email": "team@example.com"}

    def test_no_sender_fails_before_calling_sendgrid(self) -> None:
        client = _FakeHTTP()
        with pytest.raises(EmailDeliveryError, match="No sender"):
            SendGridAdapter(api_key="k", client=client).send(**MAIL, from_email="")
        assert client.calls == []

    def test_an_api_refusal_is_an_email_delivery_error(self, monkeypatch) -> None:
        import requests

        class _Response:
            status_code = 403
            text = "The from address does not match a verified Sender Identity"
            reason = "Forbidden"

        monkeypatch.setattr(requests, "post", lambda *a, **k: _Response())
        with pytest.raises(EmailDeliveryError, match="verified Sender Identity"):
            SendGridAdapter(api_key="k").send(**MAIL, from_email="x@example.com")


class TestMicrosoftOutlookAdapter:
    def _adapter(self, client: Any = None) -> MicrosoftOutlookAdapter:
        return MicrosoftOutlookAdapter(
            tenant_id="t",
            client_id="c",
            client_secret="s",
            user="team@example.com",
            client=client,
        )

    def test_an_empty_sender_sends_as_the_configured_mailbox(self) -> None:
        client = _FakeHTTP()
        self._adapter(client).send(**MAIL, from_email="")
        assert "/users/team%40example.com/sendMail" in client.calls[0][0]

    def test_a_graph_refusal_is_an_email_delivery_error(self, monkeypatch) -> None:
        import requests

        class _Response:
            status_code = 404
            text = '{"error":{"code":"ErrorInvalidUser"}}'
            reason = "Not Found"

        adapter = self._adapter()
        monkeypatch.setattr(adapter, "_get_token", lambda: "token")
        monkeypatch.setattr(requests, "post", lambda *a, **k: _Response())
        with pytest.raises(EmailDeliveryError, match="ErrorInvalidUser"):
            adapter.send(**MAIL, from_email="nobody@example.com")


class TestFilesystemAdapter:
    def test_an_empty_sender_keeps_the_mail_with_the_default(
        self, tmp_path: Path
    ) -> None:
        adapter = FilesystemAdapter(directory=str(tmp_path))
        message_id = adapter.send(**MAIL, from_email="")
        assert adapter.get_sent(message_id).summary.sender == "no-reply@localhost"

    def test_the_default_is_configurable(self, tmp_path: Path) -> None:
        adapter = FilesystemAdapter(
            directory=str(tmp_path), from_email="team@example.com"
        )
        message_id = adapter.send(**MAIL, from_email="")
        assert adapter.get_sent(message_id).summary.sender == "team@example.com"


# --- Engine configuration ----------------------------------------------------


@pytest.mark.parametrize(
    ("adapter", "config"),
    [
        ("smtp", {"host": "relay", "port": 25}),
        ("ses", {}),
        ("sendgrid", {"api_key": "k"}),
        ("filesystem", {"directory": "storage/email"}),
    ],
)
def test_the_adapter_configuration_takes_a_default_sender(
    adapter: Any, config: dict[str, Any]
) -> None:
    loaded = EmailAdapterConfiguration(
        adapter=adapter, config={**config, "from_email": "team@example.com"}
    ).load()
    assert loaded._default_from_email == "team@example.com"  # type: ignore[attr-defined]
