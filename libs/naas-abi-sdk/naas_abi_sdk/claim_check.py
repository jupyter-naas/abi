"""Pub/sub, queue and job messages above the broker limit (claim check).

A message that does not fit the connection's ``max_payload`` (header block
counted) is stored in a JetStream object store and replaced by an empty body
and a reference header; ``resolve`` reads it back on the receiving side. RPC
calls use overflow instead (``overflow.py``): a published message may have
many readers, an overflow session has one. See
docs/adr/20261003_nats-claim-check.md.

Stored values expire after ``TTL_SECONDS``: a queued or scheduled message
must be read within that time.
"""

from __future__ import annotations

import weakref
from typing import Any
from uuid import uuid4

from nats.js import api
from nats.js.errors import BadRequestError, NotFoundError

from naas_abi_sdk.messages import message_size

BUCKET = "abi_claim_checks"
HEADER = "Abi-Claim-Check"
SIZE_HEADER = "Abi-Claim-Check-Size"
MAX_VALUE_BYTES = 256 * 1024 * 1024
TTL_SECONDS = 7 * 24 * 3600

_buckets: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()


class ClaimCheckTooLarge(ValueError):
    """Above ``MAX_VALUE_BYTES`` even for the object store: use a storage reference."""


def stream_header_reserve(stream: str) -> int:
    """Bytes a JetStream publish adds for ``stream`` (Nats-Expected-Stream)."""
    return len(f"Nats-Expected-Stream: {stream}\r\n") + 16


async def _bucket(nc: Any) -> Any:
    store = _buckets.get(nc)
    if store is not None:
        return store
    js = nc.jetstream()
    try:
        store = await js.object_store(BUCKET)
    except NotFoundError:
        try:
            store = await js.create_object_store(
                BUCKET,
                config=api.ObjectStoreConfig(
                    description="NATS messages above the broker limit (claim check)",
                    ttl=TTL_SECONDS,
                ),
            )
        except BadRequestError:  # created concurrently
            store = await js.object_store(BUCKET)
    _buckets[nc] = store
    return store


async def prepare(
    nc: Any,
    payload: bytes,
    headers: dict[str, str] | None = None,
    *,
    reserve: int = 0,
) -> tuple[bytes, dict[str, str] | None]:
    """The body and headers to send: unchanged when the message fits the
    broker limit (with ``reserve`` bytes the client library adds), otherwise a
    reference to the stored payload."""
    if message_size(payload, headers) + reserve <= nc.max_payload:
        return payload, headers
    if len(payload) > MAX_VALUE_BYTES:
        raise ClaimCheckTooLarge(
            f"{len(payload)} bytes exceeds the {MAX_VALUE_BYTES}-byte message limit; "
            "use a storage reference"
        )
    name = uuid4().hex
    # The object store's own chunks must fit the broker limit too.
    chunk = min(128 * 1024, nc.max_payload // 2)
    await (await _bucket(nc)).put(
        name,
        payload,
        meta=api.ObjectMeta(
            name=name, options=api.ObjectMetaOptions(max_chunk_size=chunk)
        ),
    )
    return b"", {**(headers or {}), HEADER: name, SIZE_HEADER: str(len(payload))}


def carries_reference(msg: Any) -> bool:
    """Whether ``msg`` is a claim check (its payload is in the object store)."""
    return bool((getattr(msg, "headers", None) or {}).get(HEADER))


async def resolve(nc: Any, msg: Any) -> bytes:
    """The payload a received message carries, read back if it was stored."""
    name = (getattr(msg, "headers", None) or {}).get(HEADER)
    if not name:
        return msg.data
    return (await (await _bucket(nc)).get(name)).data


async def resolve_in_place(nc: Any, msg: Any) -> Any:
    """``msg`` with ``msg.data`` set to the payload it carries."""
    msg.data = await resolve(nc, msg)
    return msg
