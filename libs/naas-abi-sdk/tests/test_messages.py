import asyncio
from types import SimpleNamespace

import pytest
from nats.errors import MaxPayloadError

from naas_abi_sdk import messages


def test_message_size_counts_the_header_block_as_nats_does():
    assert messages.message_size(b"abc", None) == 3
    assert messages.message_size(b"abc", {}) == 3
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
        reply="_INBOX.x", _client=client, headers={"Nats-Auth-Token": "secret"}
    )

    asyncio.run(messages.reply(request, b"ok"))
    asyncio.run(messages.reply(request, b"err", {"Abi-Error-Code": "X"}))

    assert client.published == [
        ("_INBOX.x", b"ok", None),
        ("_INBOX.x", b"err", {"Abi-Error-Code": "X"}),
    ]


def test_reply_refuses_a_message_the_broker_would_close_the_connection_for():
    client = Client(64)
    request = SimpleNamespace(reply="_INBOX.x", _client=client, headers=None)
    body = b"x" * 50  # fits alone, not with the header block

    with pytest.raises(MaxPayloadError):
        asyncio.run(messages.reply(request, body, {"Abi-Error-Code": "INTERNAL"}))
    assert client.published == []


def test_reply_needs_a_reply_subject():
    request = SimpleNamespace(reply="", _client=Client(1024), headers=None)
    with pytest.raises(ValueError):
        asyncio.run(messages.reply(request, b"ok"))
