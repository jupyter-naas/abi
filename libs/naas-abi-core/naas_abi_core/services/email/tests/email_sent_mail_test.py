"""Kept sent mail: who keeps it, and the default for adapters that keep none."""

import pytest
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
from naas_abi_core.services.email.EmailPorts import IEmailAdapter, SentEmailsNotKept
from naas_abi_core.services.email.EmailService import EmailService


class _HandsOff(IEmailAdapter):
    def send(self, **kwargs):
        return None


@pytest.mark.parametrize(
    "adapter_class", [SMTPAdapter, SESAdapter, SendGridAdapter, MicrosoftOutlookAdapter]
)
def test_provider_adapters_keep_no_sent_mail(adapter_class):
    for method in ("list_sent", "get_sent", "delete_sent"):
        assert getattr(adapter_class, method) is getattr(IEmailAdapter, method)


def test_keeping_nothing_is_reported_as_such():
    adapter = _HandsOff()

    with pytest.raises(SentEmailsNotKept, match="_HandsOff keeps no sent mail"):
        adapter.list_sent()
    with pytest.raises(SentEmailsNotKept):
        adapter.get_sent("x")
    with pytest.raises(SentEmailsNotKept):
        adapter.delete_sent("x")
    assert isinstance(SentEmailsNotKept("x"), NotImplementedError)


def test_service_returns_the_kept_id_and_reads_kept_mail(tmp_path):
    service = EmailService(FilesystemAdapter(directory=str(tmp_path)))

    message_id = service.send(
        to_email="alice@example.com",
        subject="Hello",
        text_body="Hi",
        from_email="noreply@example.com",
    )

    assert message_id is not None
    assert [m.message_id for m in service.list_sent()] == [message_id]
    assert service.get_sent(message_id).summary.subject == "Hello"
    service.delete_sent(message_id)
    assert service.list_sent() == []


def test_service_passes_through_adapters_that_keep_nothing():
    service = EmailService(_HandsOff())

    assert (
        service.send(
            to_email="a@example.com",
            subject="s",
            text_body="t",
            from_email="f@example.com",
        )
        is None
    )
    with pytest.raises(SentEmailsNotKept):
        service.list_sent()
