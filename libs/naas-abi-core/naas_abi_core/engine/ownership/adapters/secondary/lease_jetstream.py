"""The engine lease as one key of a JetStream KV bucket (``ABI_ENGINE``/``owner``)."""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict

from naas_abi_core.engine.ownership.ownership_ports import (
    EngineLeasePort,
    Holder,
    LeaseConflict,
    LeaseRecord,
    LeaseTaken,
)
from nats.aio.client import Client as NATSClient
from nats.errors import TimeoutError as NATSTimeoutError
from nats.js.api import KeyValueConfig
from nats.js.errors import (
    BadRequestError,
    BucketNotFoundError,
    KeyNotFoundError,
    KeyWrongLastSequenceError,
)
from nats.js.kv import KeyValue

DEFAULT_BUCKET = "ABI_ENGINE"
KEY = "owner"
_DELETES = ("DEL", "PURGE")
# JetStream's "wrong last sequence": nats-py maps it for update, not for delete.
_WRONG_LAST_SEQUENCE = 10071


def _wrong_revision(exc: Exception) -> bool:
    return isinstance(exc, KeyWrongLastSequenceError) or (
        isinstance(exc, BadRequestError) and exc.err_code == _WRONG_LAST_SEQUENCE
    )


def _encode(holder: Holder) -> bytes:
    return json.dumps(asdict(holder), sort_keys=True).encode()


def _decode(data: bytes | None) -> Holder:
    """A value this release did not write still names a holder, just an unknown one."""
    try:
        fields = json.loads(data or b"")
    except (ValueError, UnicodeDecodeError):
        fields = {}
    if not isinstance(fields, dict):
        fields = {}

    def text(name: str) -> str:
        value = fields.get(name, "")
        return value if isinstance(value, str) else ""

    pid = fields.get("pid", 0)
    return Holder(
        instance_id=text("instance_id"),
        host=text("host"),
        pid=pid if isinstance(pid, int) else 0,
        version=text("version"),
        rollout_id=text("rollout_id"),
        started_at=text("started_at"),
    )


def _record(entry: KeyValue.Entry) -> LeaseRecord | None:
    if entry.operation in _DELETES:
        return None
    return LeaseRecord(_decode(entry.value), entry.revision or 0)


class JetStreamLease(EngineLeasePort):
    def __init__(self, bucket: KeyValue, key: str = KEY):
        self.bucket, self.key = bucket, key

    @classmethod
    async def open(cls, nc: NATSClient, bucket: str = DEFAULT_BUCKET) -> JetStreamLease:
        """The lease on ``bucket``, creating the bucket on first use."""
        js = nc.jetstream()
        try:
            kv = await js.key_value(bucket)
        except BucketNotFoundError:
            kv = await js.create_key_value(KeyValueConfig(bucket=bucket, history=1))
        return cls(kv)

    async def read(self) -> LeaseRecord | None:
        try:
            entry = await self.bucket.get(self.key)
        except KeyNotFoundError:  # KeyDeletedError included
            return None
        return _record(entry)

    async def create(self, holder: Holder) -> int:
        try:
            return await self.bucket.create(self.key, _encode(holder))
        except (KeyWrongLastSequenceError, BadRequestError) as exc:
            if not _wrong_revision(exc):
                raise
            raise LeaseTaken() from exc

    async def update(self, holder: Holder, revision: int) -> int:
        try:
            return await self.bucket.update(self.key, _encode(holder), last=revision)
        except (KeyWrongLastSequenceError, BadRequestError) as exc:
            if not _wrong_revision(exc):
                raise
            raise LeaseConflict() from exc

    async def delete(self, revision: int) -> None:
        try:
            await self.bucket.delete(self.key, last=revision)
        except (KeyWrongLastSequenceError, BadRequestError) as exc:
            if not _wrong_revision(exc):
                raise
            raise LeaseConflict() from exc

    async def wait_for_change(
        self, revision: int, timeout: float
    ) -> LeaseRecord | None:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + timeout
        watcher = await self.bucket.watch(self.key)
        try:
            while True:
                remaining = deadline - loop.time()
                if remaining <= 0:
                    return await self.read()
                try:
                    entry = await watcher.updates(timeout=remaining)
                except (TimeoutError, NATSTimeoutError):
                    return await self.read()
                if entry is None:  # the current value has been delivered
                    continue
                record = _record(entry)
                if (record.revision if record is not None else 0) != revision:
                    return record
        finally:
            await watcher.stop()
