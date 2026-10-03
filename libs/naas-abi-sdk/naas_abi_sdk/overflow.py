"""RPC overflow: payloads above the broker limit travel as transfer/v1 frames.

Shared by every protobuf RPC client (the SDK ``Transport`` and core's
``NatsRPCClient``); the engine side is ``naas_abi_core.engine.nats_overflow``.
See docs/adr/20261003_nats-rpc-overflow.md.

- A client that can read an overflowed reply sends ``ACCEPT_HEADER: 1``. The
  service then parks a reply that does not fit and answers with an empty body,
  ``REPLY_HEADER`` (the transfer id) and ``SIZE_HEADER``; ``download`` reads it.
- A request that does not fit is sent with ``upload`` first, then as an empty
  body with ``REQUEST_HEADER``; the service reads the upload before decoding.

``call(subject, request, response_type)`` is one protobuf exchange that raises
on an error reply. Nothing here retries or replays.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from naas_abi_proto.transfer.v1 import transfer_pb2 as pb

from naas_abi_sdk.transfer import Transfer, transfer_subject

PREFIX = "abi.rpc.overflow"
ACCEPT_HEADER = "Abi-Overflow"
REPLY_HEADER = "Abi-Overflow-Reply"
SIZE_HEADER = "Abi-Overflow-Size"
REQUEST_HEADER = "Abi-Overflow-Request"
UPLOAD_OPERATION = "request"
MAX_VALUE_BYTES = 256 * 1024 * 1024
CHUNK_BYTES = 1024 * 1024
MIN_CHUNK_BYTES = 1024  # transfer hosts refuse smaller chunks

Call = Callable[[str, Any, Any], Awaitable[Any]]


class OverflowRefused(RuntimeError):
    """The value cannot overflow (too large, or announced wrongly)."""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


def chunk_size(max_payload: int) -> int:
    """Chunk bytes for a broker limit: at most half a packet, at most 1 MiB."""
    return min(CHUNK_BYTES, max_payload // 2)


def possible(max_payload: int) -> bool:
    """Whether a broker limit leaves room for transfer chunks at all."""
    return chunk_size(max_payload) >= MIN_CHUNK_BYTES


def _too_large(size: int) -> OverflowRefused:
    return OverflowRefused(
        "PAYLOAD_TOO_LARGE",
        f"{size} bytes exceeds the {MAX_VALUE_BYTES}-byte overflow limit; "
        "use streaming or a storage reference",
    )


async def upload(call: Call, payload: bytes, *, chunk_bytes: int) -> str:
    """Upload a serialized request; return the transfer id to send with the call.

    The session stays open for the service to read; ``close`` it after the call.
    """
    if len(payload) > MAX_VALUE_BYTES:
        raise _too_large(len(payload))
    opened = await call(
        f"{PREFIX}.open",
        pb.OpenRequest(operation=UPLOAD_OPERATION, chunk_bytes=chunk_bytes),
        pb.OpenResponse,
    )
    try:
        await Transfer(call, PREFIX, opened.id, opened.chunk_bytes).write(payload)
    except BaseException:
        await close(call, opened.id)
        raise
    return opened.id


async def download(call: Call, transfer_id: str, size: int) -> bytes:
    """Read a parked reply of ``size`` bytes, then release it."""
    try:
        if size > MAX_VALUE_BYTES:
            raise _too_large(size)
        data = bytearray()
        async for fragment, _ in Transfer(call, PREFIX, transfer_id, 0).fragments():
            data.extend(fragment)
            if len(data) > size:
                break
        if len(data) != size:
            raise OverflowRefused(
                "INTERNAL", f"overflow reply has {len(data)} bytes, announced {size}"
            )
        return bytes(data)
    finally:
        await close(call, transfer_id)


async def close(call: Call, transfer_id: str) -> None:
    """Release a session; idle expiry applies if this fails."""
    try:
        await call(
            transfer_subject(PREFIX, "close", transfer_id),
            pb.CloseRequest(id=transfer_id),
            pb.CloseResponse,
        )
    except Exception:  # cleanup cannot replace the call's own outcome
        logging.getLogger(__name__).warning(
            "Could not close an overflow transfer; idle expiry applies", exc_info=True
        )
