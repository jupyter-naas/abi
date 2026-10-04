import asyncio
import json

import pytest
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.email_resources import (
    EmailResources,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.contracts import (
    ServiceResourcesContract,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources import (
    InvalidResource,
    ResourceNotFound,
    UnsupportedOperation,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.tests import fixtures
from naas_abi_core.services.email.adapters.secondary.FilesystemAdapter import (
    FilesystemAdapter,
)
from naas_abi_core.services.email.EmailPorts import IEmailAdapter
from naas_abi_core.services.email.EmailService import EmailService

FROM = "no-reply@nexus.example.com"


def _message(subject: str, text: str, **extra) -> bytes:
    return json.dumps({"to": "ops@example.com", "subject": subject, "text": text, **extra}).encode()


@pytest.fixture
def kept(tmp_path):
    service = EmailService(FilesystemAdapter(directory=str(tmp_path / "mail")))
    for name, value in fixtures.SEED_ITEMS.items():
        service.send(
            to_email="ops@example.com", subject=name, text_body=value.decode(), from_email=FROM
        )
    return service


class TestEmailResources(ServiceResourcesContract):
    """Seeded messages are named by subject; values are the text bodies."""

    sized = False

    @pytest.fixture
    def resources(self, kept):
        return EmailResources(kept, default_from=FROM, default_from_name="NEXUS")

    def assert_shown(self, shown, text):
        assert shown is not None and text in shown

    def assert_downloaded(self, data, text):
        assert text.encode() in data

    def test_write_creates_then_replaces(self, resources):
        """Email: creating sends a message; a sent message cannot be replaced."""
        created = asyncio.run(resources.write("draft", _message("epsilon", "new value")))

        assert (created.name, created.kind) == ("epsilon", "item")
        assert "write" not in created.actions
        assert "new value" in asyncio.run(resources.read(created.id)).content.text
        with pytest.raises(UnsupportedOperation):
            asyncio.run(resources.write(created.id, _message("again", "x")))


def test_read_shows_headers_and_the_text_body(kept):
    resources = EmailResources(kept, default_from=FROM)
    created = asyncio.run(
        resources.write(
            "x", _message("Weekly", "All good.", cc=["cto@example.com"], reply_to="ops@example.com")
        )
    )

    text = asyncio.run(resources.read(created.id)).content.text

    assert "To: ops@example.com" in text
    assert "Cc: cto@example.com" in text
    assert "Subject: Weekly" in text
    assert f"From: {FROM}" in text
    assert text.rstrip().endswith("All good.")
    assert created.attributes["to"] == "ops@example.com"


def test_messages_are_validated_before_sending(kept):
    resources = EmailResources(kept, default_from=FROM)
    before = len(kept.list_sent())

    for bad in (
        b"not json",
        b"[]",
        _message("", "x"),
        json.dumps({"subject": "s", "text": "t"}).encode(),
        json.dumps({"to": 3, "subject": "s", "text": "t"}).encode(),
        json.dumps({"to": "a@example.com", "subject": "s"}).encode(),
    ):
        with pytest.raises(InvalidResource):
            asyncio.run(resources.write("x", bad))

    assert len(kept.list_sent()) == before


class _HandsOff(IEmailAdapter):
    def __init__(self):
        self.sent = []

    def send(self, **kwargs):
        self.sent.append(kwargs)
        return None


def test_adapters_that_keep_nothing_still_send_and_list_nothing():
    adapter = _HandsOff()
    resources = EmailResources(EmailService(adapter), default_from=FROM, default_from_name="NEXUS")

    page = asyncio.run(resources.list())
    entry = asyncio.run(resources.write("hello", _message("Hello", "hi")))

    # Browsable but empty: the web shows its "nothing kept" empty state, not a lookup box.
    assert resources.capabilities.browse is True and resources.capabilities.create is True
    assert (page.listable, page.entries) == (True, ())
    assert resources.keeps_mail is False
    assert (entry.name, entry.actions) == ("Hello", ())
    assert adapter.sent[0]["from_email"] == FROM and adapter.sent[0]["from_name"] == "NEXUS"
    assert adapter.sent[0]["to_emails"] == ["ops@example.com"]
    with pytest.raises(ResourceNotFound):
        asyncio.run(resources.read("hello"))
    with pytest.raises(UnsupportedOperation):
        asyncio.run(resources.delete("hello"))


def test_read_gives_an_email_view_with_both_bodies(kept):
    resources = EmailResources(kept, default_from=FROM, default_from_name="NEXUS")
    created = asyncio.run(
        resources.write(
            "x",
            _message(
                "Launch", "Plain body.", html="<p>Rich <b>body</b></p>", cc=["cto@example.com"]
            ),
        )
    )

    view = asyncio.run(resources.read(created.id)).view

    assert view["type"] == "email"
    assert view["subject"] == "Launch"
    assert view["to"] == ["ops@example.com"]
    assert view["cc"] == ["cto@example.com"]
    assert "NEXUS" in view["from"] and FROM in view["from"]
    assert view["text"].strip() == "Plain body."
    assert "<b>body</b>" in view["html"]
    assert view["sent_at"] == created.modified
    assert view["attachments"] == []


def test_listing_summarizes_each_message_by_its_body_start(kept):
    entries = asyncio.run(EmailResources(kept, default_from=FROM).list("")).entries
    bodies = {name: value.decode() for name, value in fixtures.SEED_ITEMS.items()}

    for entry in entries:
        assert entry.attributes["snippet"] == bodies[entry.name]
        assert entry.attributes["summary"] == bodies[entry.name]
        assert entry.attributes["to"] == "ops@example.com"


def test_a_message_without_a_body_is_summarized_by_its_recipient(tmp_path):
    service = EmailService(FilesystemAdapter(directory=str(tmp_path / "mail")))
    service.send(to_email="ops@example.com", subject="empty", text_body="", from_email=FROM)

    (entry,) = asyncio.run(EmailResources(service, default_from=FROM).list("")).entries

    assert entry.attributes["summary"] == "To ops@example.com"
    assert entry.attributes["snippet"] == ""
