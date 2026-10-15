"""NATS message size and replies, as the broker counts them.

The broker's ``max_payload`` covers the body AND the header block; nats-py's
own check only covers the body, and a message over the limit makes the server
close the connection. ``Msg.respond`` also sends the request's headers back on
the reply (the caller's token included): ``reply`` never does.
"""

from __future__ import annotations

from typing import Any

from nats.errors import MaxPayloadError


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
    client = msg._client
    if message_size(data, headers) > client.max_payload:
        raise MaxPayloadError()
    await client.publish(msg.reply, data, headers=headers)
