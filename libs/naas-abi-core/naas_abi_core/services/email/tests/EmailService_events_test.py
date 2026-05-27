# mypy: disable-error-code="arg-type,misc"
from __future__ import annotations

import pytest

from naas_abi_core.services.email.EmailPorts import IEmailAdapter
from naas_abi_core.services.email.EmailService import EmailService
from naas_abi_core.services.email.ontologies.modules.EmailEventOntology import (
    EmailError,
    EmailSent,
)


class _RecordingAdapter(IEmailAdapter):
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def send(self, **kwargs) -> None:
        self.calls.append(kwargs)


class _BrokenAdapter(IEmailAdapter):
    def send(self, **kwargs) -> None:
        raise RuntimeError("SMTP down")


class _FakeEventService:
    def __init__(self) -> None:
        self.published: list = []

    def publish(self, event) -> None:
        self.published.append(event)


class _ExplodingEventService:
    def publish(self, event) -> None:
        raise RuntimeError("event bus down")


class _FakeServices:
    def __init__(self, events=None) -> None:
        self._events = events

    def events_available(self) -> bool:
        return self._events is not None

    @property
    def events(self):
        assert self._events is not None
        return self._events


def _send(svc: EmailService) -> None:
    svc.send(
        to_email="alice@example.com",
        subject="hi",
        text_body="hello",
        from_email="bot@example.com",
    )


def test_no_events_when_services_not_wired() -> None:
    adapter = _RecordingAdapter()
    svc = EmailService(adapter)
    _send(svc)
    assert len(adapter.calls) == 1


def test_no_events_when_events_unavailable() -> None:
    adapter = _RecordingAdapter()
    svc = EmailService(adapter)
    svc.set_services(_FakeServices(events=None))
    _send(svc)
    assert len(adapter.calls) == 1


def test_successful_send_emits_email_sent() -> None:
    adapter = _RecordingAdapter()
    svc = EmailService(adapter)
    events = _FakeEventService()
    svc.set_services(_FakeServices(events))

    _send(svc)

    assert len(events.published) == 1
    evt = events.published[0]
    assert isinstance(evt, EmailSent)
    assert evt.to == "alice@example.com"
    assert evt.subject == "hi"
    assert evt.sender == "bot@example.com"


def test_adapter_exception_emits_email_error_and_reraises() -> None:
    svc = EmailService(_BrokenAdapter())
    events = _FakeEventService()
    svc.set_services(_FakeServices(events))

    with pytest.raises(RuntimeError):
        _send(svc)

    errors = [e for e in events.published if isinstance(e, EmailError)]
    assert len(errors) == 1
    err = errors[0]
    assert err.to == "alice@example.com"
    assert err.subject == "hi"
    assert "SMTP down" in (err.message or "")
    assert not any(isinstance(e, EmailSent) for e in events.published)


def test_publisher_exception_does_not_break_send() -> None:
    adapter = _RecordingAdapter()
    svc = EmailService(adapter)
    svc.set_services(_FakeServices(events=_ExplodingEventService()))

    _send(svc)
    assert len(adapter.calls) == 1
