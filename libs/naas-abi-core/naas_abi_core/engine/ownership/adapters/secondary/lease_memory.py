"""An engine lease in memory: for tests and engines sharing one event loop."""

from __future__ import annotations

import asyncio

from naas_abi_core.engine.ownership.ownership_ports import (
    EngineLeasePort,
    Holder,
    LeaseConflict,
    LeaseRecord,
    LeaseTaken,
)


class InMemoryLease(EngineLeasePort):
    def __init__(self) -> None:
        self._record: LeaseRecord | None = None
        self._last_revision = 0
        self._changed: asyncio.Condition | None = None

    @property
    def _condition(self) -> asyncio.Condition:
        # Created on first use, so it belongs to the loop that uses it.
        if self._changed is None:
            self._changed = asyncio.Condition()
        return self._changed

    def _revision(self) -> int:
        return self._record.revision if self._record is not None else 0

    async def _write(self, record: LeaseRecord | None) -> None:
        async with self._condition:
            self._record = record
            self._condition.notify_all()

    def _next(self, holder: Holder) -> LeaseRecord:
        self._last_revision += 1
        return LeaseRecord(holder, self._last_revision)

    async def read(self) -> LeaseRecord | None:
        return self._record

    async def create(self, holder: Holder) -> int:
        if self._record is not None:
            raise LeaseTaken()
        record = self._next(holder)
        await self._write(record)
        return record.revision

    async def update(self, holder: Holder, revision: int) -> int:
        if self._record is None or self._record.revision != revision:
            raise LeaseConflict()
        record = self._next(holder)
        await self._write(record)
        return record.revision

    async def delete(self, revision: int) -> None:
        if self._record is None or self._record.revision != revision:
            raise LeaseConflict()
        self._last_revision += 1  # a delete is a write, as in a KV store
        await self._write(None)

    async def wait_for_change(
        self, revision: int, timeout: float
    ) -> LeaseRecord | None:
        async with self._condition:
            try:
                await asyncio.wait_for(
                    self._condition.wait_for(lambda: self._revision() != revision),
                    timeout,
                )
            except TimeoutError:
                pass
            return self._record
