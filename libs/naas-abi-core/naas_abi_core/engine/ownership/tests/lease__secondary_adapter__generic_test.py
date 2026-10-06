"""Contract every engine lease adapter must meet (docs/adr/20261006_single-serving-engine.md).

An adapter's test subclasses ``GenericLeaseAdapterTest`` and implements
``open_lease``: an async context manager yielding a lease on an empty store.
"""

import asyncio
import time
from abc import ABC, abstractmethod
from contextlib import AbstractAsyncContextManager

import pytest
from naas_abi_core.engine.ownership.ownership_ports import (
    EngineLeasePort,
    Holder,
    LeaseConflict,
    LeaseTaken,
)


def holder(name: str = "a", rollout_id: str = "") -> Holder:
    return Holder(
        instance_id=f"engine-{name}",
        host=f"host-{name}",
        pid=1000,
        version="1.2.3",
        rollout_id=rollout_id,
        started_at="2026-10-06T10:00:00+00:00",
    )


class GenericLeaseAdapterTest(ABC):
    @abstractmethod
    def open_lease(self) -> AbstractAsyncContextManager[EngineLeasePort]:
        raise NotImplementedError()

    def run(self, scenario) -> None:
        async def main():
            async with self.open_lease() as lease:
                await scenario(lease)

        asyncio.run(main())

    def test_an_empty_store_has_no_record(self):
        async def scenario(lease):
            assert await lease.read() is None

        self.run(scenario)

    def test_create_records_the_holder_with_a_revision(self):
        async def scenario(lease):
            revision = await lease.create(holder("a", "r1"))

            record = await lease.read()
            assert revision > 0
            assert record is not None
            assert record.revision == revision
            assert record.holder == holder("a", "r1")

        self.run(scenario)

    def test_create_fails_while_a_record_exists(self):
        async def scenario(lease):
            await lease.create(holder("a"))

            with pytest.raises(LeaseTaken):
                await lease.create(holder("b"))
            assert (await lease.read()).holder == holder("a")

        self.run(scenario)

    def test_update_at_the_current_revision_moves_it_forward(self):
        async def scenario(lease):
            first = await lease.create(holder("a"))

            second = await lease.update(holder("b"), first)

            record = await lease.read()
            assert second > first
            assert record.revision == second
            assert record.holder == holder("b")

        self.run(scenario)

    def test_an_update_with_the_same_holder_still_moves_the_revision(self):
        async def scenario(lease):
            first = await lease.create(holder("a"))

            assert await lease.update(holder("a"), first) > first

        self.run(scenario)

    def test_update_at_a_stale_revision_conflicts(self):
        async def scenario(lease):
            first = await lease.create(holder("a"))
            await lease.update(holder("a"), first)

            with pytest.raises(LeaseConflict):
                await lease.update(holder("b"), first)
            assert (await lease.read()).holder == holder("a")

        self.run(scenario)

    def test_update_of_a_missing_record_conflicts(self):
        async def scenario(lease):
            with pytest.raises(LeaseConflict):
                await lease.update(holder("a"), 1)

        self.run(scenario)

    def test_delete_at_the_current_revision_frees_the_lease(self):
        async def scenario(lease):
            revision = await lease.create(holder("a"))

            await lease.delete(revision)

            assert await lease.read() is None
            assert await lease.create(holder("b")) > revision

        self.run(scenario)

    def test_delete_at_a_stale_revision_conflicts_and_keeps_the_record(self):
        async def scenario(lease):
            first = await lease.create(holder("a"))
            await lease.update(holder("b"), first)

            with pytest.raises(LeaseConflict):
                await lease.delete(first)
            assert (await lease.read()).holder == holder("b")

        self.run(scenario)

    def test_wait_for_change_returns_the_current_record_after_the_timeout(self):
        async def scenario(lease):
            revision = await lease.create(holder("a"))

            started = time.monotonic()
            record = await lease.wait_for_change(revision, timeout=0.3)

            assert time.monotonic() - started >= 0.25
            assert record.revision == revision

        self.run(scenario)

    def test_wait_for_change_wakes_on_an_update(self):
        async def scenario(lease):
            revision = await lease.create(holder("a"))

            async def renew_soon():
                await asyncio.sleep(0.1)
                await lease.update(holder("a"), revision)

            started = time.monotonic()
            renewal = asyncio.create_task(renew_soon())
            record = await lease.wait_for_change(revision, timeout=5)
            await renewal

            assert time.monotonic() - started < 2
            assert record.revision > revision

        self.run(scenario)

    def test_wait_for_change_wakes_on_a_delete(self):
        async def scenario(lease):
            revision = await lease.create(holder("a"))

            async def release_soon():
                await asyncio.sleep(0.1)
                await lease.delete(revision)

            started = time.monotonic()
            release = asyncio.create_task(release_soon())
            record = await lease.wait_for_change(revision, timeout=5)
            await release

            assert time.monotonic() - started < 2
            assert record is None

        self.run(scenario)

    def test_wait_for_change_from_empty_wakes_on_a_create(self):
        async def scenario(lease):
            async def create_soon():
                await asyncio.sleep(0.1)
                await lease.create(holder("a"))

            creation = asyncio.create_task(create_soon())
            record = await lease.wait_for_change(0, timeout=5)
            await creation

            assert record is not None
            assert record.holder == holder("a")

        self.run(scenario)

    def test_wait_for_change_returns_at_once_if_already_changed(self):
        async def scenario(lease):
            first = await lease.create(holder("a"))
            await lease.update(holder("a"), first)

            started = time.monotonic()
            record = await lease.wait_for_change(first, timeout=5)

            assert time.monotonic() - started < 2
            assert record.revision > first

        self.run(scenario)
