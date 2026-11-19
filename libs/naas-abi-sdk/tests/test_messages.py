import asyncio
from types import SimpleNamespace

import pytest
from nats.errors import MaxPayloadError

from naas_abi_sdk import messages


def test_message_size_counts_the_header_block_as_nats_does():
    assert messages.message_size(b"abc", None) == 3
    # nats-py sends a header block for any headers that are not None, even {}.
    assert messages.message_size(b"abc", {}) == 3 + len("NATS/1.0\r\n\r\n")
    block = "NATS/1.0\r\nA: b\r\n\r\n"
    assert messages.message_size(b"abc", {"A": "b"}) == 3 + len(block)


class Client:
    def __init__(self, max_payload):
        self.max_payload = max_payload
        self.published = []

    async def publish(self, subject, data, headers=None):
        self.published.append((subject, data, headers))


def test_reply_never_echoes_the_requests_headers():
    client = Client(1024)
    request = SimpleNamespace(
        reply="_INBOX.x.1", _client=client, headers={"Nats-Auth-Token": "secret"}
    )

    asyncio.run(messages.reply(request, b"ok"))
    asyncio.run(messages.reply(request, b"err", {"Abi-Error-Code": "X"}))

    assert client.published == [
        ("_INBOX.x.1", b"ok", None),
        ("_INBOX.x.1", b"err", {"Abi-Error-Code": "X"}),
    ]


def test_reply_refuses_a_message_the_broker_would_close_the_connection_for():
    client = Client(64)
    request = SimpleNamespace(reply="_INBOX.x.1", _client=client, headers=None)
    body = b"x" * 50  # fits alone, not with the header block

    with pytest.raises(MaxPayloadError):
        asyncio.run(messages.reply(request, body, {"Abi-Error-Code": "INTERNAL"}))
    assert client.published == []


def test_reply_needs_a_reply_subject():
    request = SimpleNamespace(reply="", _client=Client(1024), headers=None)
    with pytest.raises(ValueError):
        asyncio.run(messages.reply(request, b"ok"))


def test_replies_go_to_inboxes_only():
    from naas_abi_sdk.messages import reply_allowed

    assert reply_allowed("_INBOX.abcdefghijklmnop.x")
    for subject in (
        None,
        "",
        "$JS.API.STREAM.PURGE.ABI_JOBS_default",
        "abi.iam.v1.changed",
        "_INBOX.>",
        "_INBOX.*",
        "_INBOXX.x",
    ):
        assert not reply_allowed(subject), subject


class PredictableConnection:
    """A module's connection whose own inboxes follow one another, as nats-py's do."""

    def __init__(self):
        self.count = 0

    def new_inbox(self):
        self.count += 1
        return f"{messages.module_inbox_prefix('key')}.{self.count}"


def test_stream_inbox_keeps_its_name_to_whom_it_is_handed():
    nc = PredictableConnection()
    first, second = messages.stream_inbox(nc), messages.stream_inbox(nc)
    # Under the connection's own inboxes, then a secret nobody can predict.
    assert first.startswith("_INBOX.key.m.1.stream.")
    assert second.startswith("_INBOX.key.m.2.stream.")
    secrets = {inbox.rsplit(".", 1)[1] for inbox in (first, second)}
    assert len(secrets) == 2 and all(len(s) >= 32 for s in secrets)
    assert messages.is_stream_inbox(first) and messages.is_stream_inbox(second)
    # Another connection's (no module prefix).
    assert messages.is_stream_inbox("_INBOX.abc.stream." + "a" * 32)


@pytest.mark.parametrize(
    "subject",
    [
        "_INBOX.key.m.1",  # an inbox anyone who saw the connection's replies predicts
        "_INBOX.key.m.1.stream.short",
        "_INBOX.>",
        "_INBOX.*.stream." + "a" * 32,
        "_INBOX.key.m.1.stream." + "a" * 31 + ">",
        "abi.svc.document.v1.put.stream." + "a" * 32,
        "_INBOX.a.b.c.stream." + "a" * 32,
        "_INBOX.key.1.stream." + "a" * 32,
        None,
    ],
)
def test_stream_inbox_keeps_out_what_is_not_one(subject):
    assert not messages.is_stream_inbox(subject)


@pytest.mark.parametrize(
    "subject",
    [
        "_INBOX.AbCd1234.AbCd5678ef",  # an engine connection's request reply
        "_INBOX.key.m.AbCd1234.AbCd5678ef",  # a module's request reply
        "_INBOX.key.m.1.stream." + "a" * 32,
    ],
)
def test_reply_keeps_to_reply_and_stream_inboxes(subject):
    assert messages.reply_allowed(subject)


@pytest.mark.parametrize(
    "subject",
    [
        "_INBOX.AbCd1234",  # a connection's own inbox: where JetStream delivers
        "_INBOX.key.m.AbCd1234",
        "_INBOX.key.m.a.b.c",
        "_INBOX.>",
        "_INBOX.a.*",
        "$JS.API.STREAM.PURGE.x",
        "abi.mod.p.x.call",
        None,
    ],
)
def test_reply_keeps_out_of_a_connections_own_inboxes(subject):
    assert not messages.reply_allowed(subject)
