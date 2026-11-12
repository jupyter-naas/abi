"""NATS message size and replies, as the broker counts them.

The broker's ``max_payload`` covers the body AND the header block; nats-py's
own check only covers the body, and a message over the limit makes the server
close the connection. ``Msg.respond`` also sends the request's headers back on
the reply (the caller's token included): ``reply`` never does.

A request's reply subject is chosen by whoever sent it. Answered with the
responder's own rights, a reply aimed at ``$JS.API.STREAM.PURGE.<stream>`` or
at another module's subjects would act there. So every responder answers only
reply subjects under ``_INBOX.`` (``reply_allowed``), where every client
receives its replies and nothing else listens.

A module's connection names its inboxes ``_INBOX.<key id>.m.<nuid>``
(``MODULE_INBOX_TOKEN``), any other connection ``_INBOX.<nuid>``. The broker
lets a module publish to inboxes of two shapes only (core
``services/iam/broker.py``): the reply subject of a request
(``<response inbox>.<token>``), and a stream inbox (``stream_inbox``), where an
agent run's updates are pushed or a body is pulled. A stream inbox ends with a
secret of its own, so only the two parties the stream was set up between can
name it. A connection's own inboxes, which anyone who saw one of its reply
subjects could predict, are never another module's to publish to.
"""

from __future__ import annotations

import re
import secrets
from typing import Any

from nats.errors import MaxPayloadError

REPLY_PREFIX = "_INBOX."
# A module's connection's inboxes: ``_INBOX.<key id>.m.<nuid>`` (core's
# ``broker.MODULE_INBOX_TOKEN``; a test keeps them equal).
MODULE_INBOX_TOKEN = "m"
# A stream inbox: ``<an inbox of the connection>.stream.<secret>``.
STREAM_TOKEN = "stream"
_TOKEN = r"[A-Za-z0-9_-]{1,64}"
_STREAM_INBOX = re.compile(
    rf"_INBOX\.(?:{_TOKEN}\.{MODULE_INBOX_TOKEN}\.)?{_TOKEN}"
    rf"\.{STREAM_TOKEN}\.[A-Za-z0-9_-]{{32,64}}"
)


def module_inbox_prefix(key_id: str) -> str:
    """The inbox prefix of a module's connection logged in with ``key_id``."""
    return f"_INBOX.{key_id}.{MODULE_INBOX_TOKEN}"


def stream_inbox(nc: Any) -> str:
    """A new inbox of ``nc`` for one stream, ending with a secret (192 bits):
    nobody can name it but who it is handed to."""
    return f"{nc.new_inbox()}.{STREAM_TOKEN}.{secrets.token_urlsafe(24)}"


def is_stream_inbox(subject: object) -> bool:
    """Whether ``subject`` is a stream inbox (``stream_inbox``), no wildcard."""
    return isinstance(subject, str) and _STREAM_INBOX.fullmatch(subject) is not None


class ReplyRefused(ValueError):
    """The request's reply subject is not an inbox: nothing is sent."""


# The reply subject of a request (nats-py's ``<response inbox>.<token>``): an
# engine connection's ``_INBOX.<nuid>.<token>``, a module's
# ``_INBOX.<key id>.m.<nuid>.<token>`` (core's ``broker.REPLY_INBOXES``).
_REPLY_INBOX = re.compile(
    rf"_INBOX\.(?:{_TOKEN}\.{MODULE_INBOX_TOKEN}\.)?{_TOKEN}\.{_TOKEN}"
)


def reply_allowed(subject: object) -> bool:
    """Whether a responder may answer on ``subject``: the reply subject of a
    request, or a stream inbox, no wildcard. Never a connection's own inbox
    (where JetStream delivers), whoever names it as a reply: a responder with
    more rights than the requester would publish there for it."""
    return isinstance(subject, str) and (
        _REPLY_INBOX.fullmatch(subject) is not None or is_stream_inbox(subject)
    )


def message_size(payload: bytes, headers: dict[str, str] | None) -> int:
    """Bytes NATS counts against max_payload: the body and the header block.

    The one copy of this rule: core and the SDK import it. nats-py sends a
    header block whenever ``headers`` is not None, even an empty one.
    """
    if headers is None:
        return len(payload)
    block = "".join(f"{key}: {value}\r\n" for key, value in headers.items())
    return len(payload) + len(f"NATS/1.0\r\n{block}\r\n".encode())


async def reply(msg: Any, data: bytes, headers: dict[str, str] | None = None) -> None:
    """Answer ``msg`` with ``data`` and only ``headers``; ``MaxPayloadError``
    when the message would exceed the connection's limit (nothing is sent)."""
    if not msg.reply:
        raise ValueError("no reply subject available")
    if not reply_allowed(msg.reply):
        raise ReplyRefused(f"not answering on {msg.reply!r}: replies go to inboxes")
    client = msg._client
    if message_size(data, headers) > client.max_payload:
        raise MaxPayloadError()
    await client.publish(msg.reply, data, headers=headers)
