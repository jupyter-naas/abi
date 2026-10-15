"""Pub/sub, queue and job messages above the broker limit (claim check).

A message that does not fit the connection's ``max_payload`` (header block
counted) is stored in the JetStream stream ``ABI_CLAIM_CHECKS`` and replaced by
an empty body and a reference header; ``resolve`` reads it back on the
receiving side. RPC calls use overflow instead (``overflow.py``): a published
message may have many readers, an overflow session has one. See
docs/adr/20261003_nats-claim-check.md.

A stored payload lives under the subjects of its **scope**, the thing it
travels with: ``abi.cc.<scope>.<id>.<chunk>``.

* ``topic_scope(topic)``: a bus topic. Whoever may use the topic may write and
  read its claim checks, nothing else (the broker grants them with the topic).
* ``job_scope(project, module_hash)``: a module's job triggers. Whoever may
  trigger the job writes, its host reads.

Chunks are read back with direct gets on their exact subjects, and the payload
is checked against the SHA-256 in the reference. Stored values expire after
``TTL_SECONDS``: a queued or scheduled message must be read within that time.
Messages stored by an earlier release in the object store bucket
``abi_claim_checks`` are still read.
"""

from __future__ import annotations

import hashlib
import weakref
from typing import Any
from uuid import uuid4

from nats.js import api
from nats.js.errors import BadRequestError, NotFoundError

from naas_abi_sdk.messages import message_size

STREAM = "ABI_CLAIM_CHECKS"
SUBJECT_PREFIX = "abi.cc"
HEADER = "Abi-Claim-Check"
SIZE_HEADER = "Abi-Claim-Check-Size"
CHUNKS_HEADER = "Abi-Claim-Check-Chunks"
SHA256_HEADER = "Abi-Claim-Check-Sha256"
MAX_VALUE_BYTES = 256 * 1024 * 1024
MAX_CHUNK_BYTES = 1024 * 1024
TTL_SECONDS = 7 * 24 * 3600
# Bytes a stored chunk's own headers and subject may take, under max_payload.
_CHUNK_OVERHEAD = 1024
# The object store of earlier releases, read only.
LEGACY_BUCKET = "abi_claim_checks"

_buckets: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()


class ClaimCheckTooLarge(ValueError):
    """Above ``MAX_VALUE_BYTES`` even for the stream: use a storage reference."""


class ClaimCheckInvalid(ValueError):
    """A stored payload is missing, or not the one the reference names."""


def topic_scope(topic: str) -> str:
    """The scope of a bus topic's claim checks (one subject token)."""
    return "t." + hashlib.sha256(topic.encode()).hexdigest()[:32]


def job_scope(project: str, module_hash: str) -> str:
    """The scope of the triggers of a module's jobs (``JobSubjects.module_hash``)."""
    return f"j.{project}.{module_hash}"


def stream_config() -> api.StreamConfig:
    """The stream the engine creates (and a broker without confinement lets
    the first writer create)."""
    return api.StreamConfig(
        name=STREAM,
        description="NATS messages above the broker limit (claim check)",
        subjects=[f"{SUBJECT_PREFIX}.>"],
        max_age=TTL_SECONDS,
        allow_direct=True,
        storage=api.StorageType.FILE,
    )


def stream_header_reserve(stream: str) -> int:
    """Bytes a JetStream publish adds for ``stream`` (Nats-Expected-Stream)."""
    return len(f"Nats-Expected-Stream: {stream}\r\n") + 16


async def ensure_stream(nc: Any) -> None:
    """Create ``ABI_CLAIM_CHECKS`` if it is missing."""
    js = nc.jetstream()
    try:
        await js.stream_info(STREAM)
    except NotFoundError:
        try:
            await js.add_stream(stream_config())
        except BadRequestError:  # created concurrently
            await js.stream_info(STREAM)


async def prepare(
    nc: Any,
    payload: bytes,
    headers: dict[str, str] | None = None,
    *,
    scope: str,
    reserve: int = 0,
    store: ThroughEngine | None = None,
) -> tuple[bytes, dict[str, str] | None]:
    """The body and headers to send: unchanged when the message fits the
    broker limit (with ``reserve`` bytes the client library adds), otherwise a
    reference to the payload, stored under ``scope``.

    ``store``: behind the broker's auth callout, the engine creates the stream
    when a write finds it missing (``ThroughEngine``); by default this
    connection does (``ensure_stream``)."""
    from nats.js.errors import NoStreamResponseError

    if message_size(payload, headers) + reserve <= nc.max_payload:
        return payload, headers
    if len(payload) > MAX_VALUE_BYTES:
        raise ClaimCheckTooLarge(
            f"{len(payload)} bytes exceeds the {MAX_VALUE_BYTES}-byte message limit; "
            "use a storage reference"
        )
    reference = f"{SUBJECT_PREFIX}.{scope}.{uuid4().hex}"
    chunk = max(1024, min(MAX_CHUNK_BYTES, nc.max_payload - _CHUNK_OVERHEAD))
    js = nc.jetstream()
    count = 0
    for start in range(0, len(payload), chunk):
        piece = payload[start : start + chunk]
        try:
            await js.publish(f"{reference}.{count}", piece, stream=STREAM)
        except NoStreamResponseError:
            if count:
                raise
            await (store.ensure(nc) if store is not None else ensure_stream(nc))
            await js.publish(f"{reference}.{count}", piece, stream=STREAM)
        count += 1
    return b"", {
        **(headers or {}),
        HEADER: reference,
        SIZE_HEADER: str(len(payload)),
        CHUNKS_HEADER: str(count),
        SHA256_HEADER: hashlib.sha256(payload).hexdigest(),
    }


def carries_reference(msg: Any) -> bool:
    """Whether ``msg`` is a claim check (its payload is stored)."""
    return bool((getattr(msg, "headers", None) or {}).get(HEADER))


class ThroughEngine:
    """Claim checks behind the broker's auth callout: the engine creates the
    stream and reads chunks back for a module (``read_claim_check``), which
    reads none by direct get. Without an engine answering, this connection
    does both."""

    def __init__(self, control: Any) -> None:
        self.control = control  # a naas_abi_sdk.broker_control.BrokerControl

    async def ensure(self, nc: Any) -> None:
        if await self.control.request("ensure_claim_checks") is None:
            await ensure_stream(nc)

    async def read(self, nc: Any, reference: str, index: int) -> bytes:
        data = await self.control.read(
            "read_claim_check", reference=reference, index=index
        )
        if data is None:
            return await _direct_chunk(nc, reference, index)
        return data


async def _direct_chunk(nc: Any, reference: str, index: int) -> bytes:
    try:
        stored = await nc.jetstream().get_msg(
            STREAM, subject=f"{reference}.{index}", direct=True
        )
    except NotFoundError:
        raise ClaimCheckInvalid(
            "The stored payload expired or was never stored"
        ) from None
    return stored.data or b""


async def resolve(nc: Any, msg: Any, *, store: ThroughEngine | None = None) -> bytes:
    """The payload a received message carries, read back if it was stored
    (through the engine with ``store``)."""
    headers = getattr(msg, "headers", None) or {}
    reference = headers.get(HEADER)
    if not reference:
        return msg.data
    if not reference.startswith(f"{SUBJECT_PREFIX}."):
        return await _legacy(nc, reference)
    try:
        count = int(headers.get(CHUNKS_HEADER, ""))
        size = int(headers.get(SIZE_HEADER, ""))
    except ValueError:
        raise ClaimCheckInvalid("Malformed claim check reference") from None
    if not 0 < count <= MAX_VALUE_BYTES // 1024 or not 0 <= size <= MAX_VALUE_BYTES:
        raise ClaimCheckInvalid("Malformed claim check reference")
    parts: list[bytes] = []
    received = 0
    for index in range(count):
        if store is not None:
            chunk = await store.read(nc, reference, index)
        else:
            chunk = await _direct_chunk(nc, reference, index)
        received += len(chunk)
        if received > size:
            raise ClaimCheckInvalid("The stored payload is larger than announced")
        parts.append(chunk)
    payload = b"".join(parts)
    if len(payload) != size or hashlib.sha256(payload).hexdigest() != headers.get(
        SHA256_HEADER
    ):
        raise ClaimCheckInvalid("The stored payload is not the one referenced")
    return payload


async def _legacy(nc: Any, name: str) -> bytes:
    store = _buckets.get(nc)
    if store is None:
        store = await nc.jetstream().object_store(LEGACY_BUCKET)
        _buckets[nc] = store
    return (await store.get(name)).data


async def resolve_in_place(
    nc: Any, msg: Any, *, store: ThroughEngine | None = None
) -> Any:
    """``msg`` with ``msg.data`` set to the payload it carries."""
    msg.data = await resolve(nc, msg, store=store)
    return msg
