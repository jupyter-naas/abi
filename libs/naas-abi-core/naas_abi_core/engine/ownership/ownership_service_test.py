import asyncio
import time

import pytest
from naas_abi_core.engine.ownership.adapters.secondary.lease_memory import InMemoryLease
from naas_abi_core.engine.ownership.ownership_ports import (
    EngineLeasePort,
    Holder,
    LeaseRecord,
)
from naas_abi_core.engine.ownership.ownership_service import (
    Claim,
    EngineAlreadyServing,
    EngineOwnership,
    LocalBackendsCannotHandOver,
    OwnershipState,
    OwnershipTiming,
    StandbyTimedOut,
    require_shared_backends,
)
from naas_abi_core.engine.ownership.tests.lease__secondary_adapter__generic_test import (
    holder,
)

# Renew every 0.1 s, fence after 0.2 s, take over after 0.4 s of silence.
TIMING = OwnershipTiming(lease_seconds=0.4, standby_timeout_seconds=5)


class FlakyLease(EngineLeasePort):
    """Shares a store with other engines; can fail this engine's calls."""

    def __init__(self, inner: EngineLeasePort):
        self.inner = inner
        self.failing = False
        self.lose_next_update_reply = False

    def _check(self) -> None:
        if self.failing:
            raise ConnectionError("broker unreachable")

    async def read(self) -> LeaseRecord | None:
        self._check()
        return await self.inner.read()

    async def create(self, holder: Holder) -> int:
        self._check()
        return await self.inner.create(holder)

    async def update(self, holder: Holder, revision: int) -> int:
        self._check()
        updated = await self.inner.update(holder, revision)
        if self.lose_next_update_reply:
            self.lose_next_update_reply = False
            raise ConnectionError("reply lost after commit")
        return updated

    async def delete(self, revision: int) -> None:
        self._check()
        await self.inner.delete(revision)

    async def wait_for_change(self, revision: int, timeout: float):
        self._check()
        return await self.inner.wait_for_change(revision, timeout)


class Serving:
    """An engine that holds the lease and keeps it, recording its callbacks."""

    def __init__(self, lease: EngineLeasePort, me: Holder, timing=TIMING):
        self.ownership = EngineOwnership(lease, me, timing)
        self.events: list[tuple[str, float]] = []
        self.task: asyncio.Task | None = None

    async def start(self) -> "Serving":
        assert await self.ownership.claim() is Claim.SERVING
        self.task = asyncio.create_task(
            self.ownership.keep(
                on_fenced=self._record("fenced"),
                on_restored=self._record("restored"),
                on_lost=self._record("lost"),
            )
        )
        return self

    def _record(self, name: str):
        async def callback() -> None:
            self.events.append((name, time.monotonic()))

        return callback

    def names(self) -> list[str]:
        return [name for name, _ in self.events]

    async def crash(self) -> None:
        """Stop renewing without releasing, as a killed process would."""
        assert self.task is not None
        self.task.cancel()
        await asyncio.gather(self.task, return_exceptions=True)

    async def stop(self) -> None:
        await self.ownership.release()
        if self.task is not None:
            await asyncio.wait_for(self.task, timeout=2)


def run(scenario) -> None:
    asyncio.run(scenario())


# --- starting a serving engine ---------------------------------------------------------


def test_a_free_lease_is_taken_at_once():
    async def scenario():
        lease = InMemoryLease()
        ownership = EngineOwnership(lease, holder("me"), TIMING)

        started = time.monotonic()
        assert await ownership.claim() is Claim.SERVING

        assert time.monotonic() - started < 0.2
        assert ownership.state is OwnershipState.SERVING
        assert (await lease.read()).holder == holder("me")

    run(scenario)


def test_a_live_engine_without_a_rollout_makes_a_new_one_fail():
    async def scenario():
        lease = InMemoryLease()
        other = await Serving(lease, holder("other")).start()

        with pytest.raises(EngineAlreadyServing) as raised:
            await EngineOwnership(lease, holder("me"), TIMING).claim()

        assert raised.value.holder == holder("other")
        assert "host-other" in str(raised.value)
        assert "1.2.3" in str(raised.value)
        await other.stop()

    run(scenario)


def test_the_live_engine_s_own_rollout_makes_a_new_one_fail():
    async def scenario():
        lease = InMemoryLease()
        other = await Serving(lease, holder("other", "r1")).start()

        with pytest.raises(EngineAlreadyServing):
            await EngineOwnership(lease, holder("me", "r1"), TIMING).claim()
        await other.stop()

    run(scenario)


def test_a_dead_engine_is_taken_over_after_one_lease_period():
    async def scenario():
        lease = InMemoryLease()
        await lease.create(holder("dead"))
        ownership = EngineOwnership(lease, holder("me"), TIMING)

        started = time.monotonic()
        assert await ownership.claim() is Claim.SERVING

        assert time.monotonic() - started >= TIMING.lease_seconds * 0.9
        assert (await lease.read()).holder == holder("me")

    run(scenario)


def test_a_new_rollout_stands_by_at_once_behind_a_live_engine():
    async def scenario():
        lease = InMemoryLease()
        other = await Serving(lease, holder("other", "r1")).start()
        ownership = EngineOwnership(lease, holder("me", "r2"), TIMING)

        started = time.monotonic()
        assert await ownership.claim() is Claim.STANDBY

        assert time.monotonic() - started < 0.2
        assert ownership.state is OwnershipState.STANDBY
        assert (await lease.read()).holder == holder("other", "r1")
        await other.stop()

    run(scenario)


def test_a_rollout_stands_by_behind_an_engine_started_without_one():
    async def scenario():
        lease = InMemoryLease()
        other = await Serving(lease, holder("other")).start()

        assert (
            await EngineOwnership(lease, holder("me", "r2"), TIMING).claim()
            is Claim.STANDBY
        )
        await other.stop()

    run(scenario)


# --- standby ---------------------------------------------------------------------------


def test_standby_takes_over_as_soon_as_the_engine_releases():
    async def scenario():
        lease = InMemoryLease()
        other = await Serving(lease, holder("other", "r1")).start()
        ownership = EngineOwnership(lease, holder("me", "r2"), TIMING)
        assert await ownership.claim() is Claim.STANDBY
        waiting = asyncio.create_task(ownership.wait_for_lease())
        await asyncio.sleep(0.2)
        assert not waiting.done()

        released = time.monotonic()
        await other.stop()
        await asyncio.wait_for(waiting, timeout=2)

        assert time.monotonic() - released < TIMING.lease_seconds / 2
        assert ownership.state is OwnershipState.SERVING
        assert (await lease.read()).holder == holder("me", "r2")

    run(scenario)


def test_standby_takes_over_from_an_engine_that_died():
    async def scenario():
        lease = InMemoryLease()
        other = await Serving(lease, holder("other", "r1")).start()
        ownership = EngineOwnership(lease, holder("me", "r2"), TIMING)
        assert await ownership.claim() is Claim.STANDBY

        died = time.monotonic()
        await other.crash()
        await asyncio.wait_for(ownership.wait_for_lease(), timeout=3)

        assert time.monotonic() - died >= TIMING.lease_seconds * 0.9
        assert (await lease.read()).holder == holder("me", "r2")

    run(scenario)


def test_standby_gives_up_after_its_timeout():
    async def scenario():
        lease = InMemoryLease()
        other = await Serving(lease, holder("other", "r1")).start()
        timing = OwnershipTiming(lease_seconds=0.4, standby_timeout_seconds=0.6)
        ownership = EngineOwnership(lease, holder("me", "r2"), timing)
        assert await ownership.claim() is Claim.STANDBY

        started = time.monotonic()
        with pytest.raises(StandbyTimedOut):
            await ownership.wait_for_lease()

        assert 0.5 <= time.monotonic() - started < 2
        await other.stop()

    run(scenario)


def test_standby_fails_when_its_own_rollout_takes_the_lease_first():
    async def scenario():
        lease = InMemoryLease()
        await lease.create(holder("other", "r1"))
        ownership = EngineOwnership(lease, holder("me", "r2"), TIMING)
        assert await ownership.claim() is Claim.STANDBY
        waiting = asyncio.create_task(ownership.wait_for_lease())
        await asyncio.sleep(0.05)

        current = await lease.read()
        await lease.update(holder("twin", "r2"), current.revision)

        with pytest.raises(EngineAlreadyServing) as raised:
            await asyncio.wait_for(waiting, timeout=2)
        assert raised.value.holder == holder("twin", "r2")

    run(scenario)


# --- serving ---------------------------------------------------------------------------


def test_a_serving_engine_keeps_renewing_until_it_releases():
    async def scenario():
        lease = InMemoryLease()
        me = await Serving(lease, holder("me")).start()
        first = (await lease.read()).revision

        await asyncio.sleep(TIMING.lease_seconds)

        assert (await lease.read()).revision >= first + 2
        await me.stop()
        assert await lease.read() is None
        assert me.ownership.state is OwnershipState.RELEASED
        assert me.names() == []

    run(scenario)


def test_release_never_deletes_another_engine_s_lease():
    async def scenario():
        lease = InMemoryLease()
        ownership = EngineOwnership(lease, holder("me"), TIMING)
        await ownership.claim()
        current = await lease.read()
        await lease.update(holder("other"), current.revision)

        await ownership.release()

        assert (await lease.read()).holder == holder("other")

    run(scenario)


def test_an_engine_that_cannot_renew_fences_itself_then_restores():
    async def scenario():
        lease = FlakyLease(InMemoryLease())
        me = await Serving(lease, holder("me")).start()

        lease.failing = True
        await asyncio.sleep(TIMING.lease_seconds * 0.75)
        assert me.names() == ["fenced"]
        assert me.ownership.state is OwnershipState.FENCED

        lease.failing = False
        await asyncio.sleep(TIMING.lease_seconds / 2)
        assert me.names() == ["fenced", "restored"]
        assert me.ownership.state is OwnershipState.SERVING
        await me.stop()

    run(scenario)


def test_an_engine_fences_itself_before_a_standby_can_take_over():
    async def scenario():
        store = InMemoryLease()
        mine = FlakyLease(store)
        me = await Serving(mine, holder("me", "r1")).start()
        standby = EngineOwnership(store, holder("next", "r2"), TIMING)
        assert await standby.claim() is Claim.STANDBY
        waiting = asyncio.create_task(standby.wait_for_lease())

        mine.failing = True
        await asyncio.wait_for(waiting, timeout=3)
        took_over = time.monotonic()

        fenced = dict(me.events)["fenced"]
        assert fenced < took_over - TIMING.lease_seconds / 4

        mine.failing = False
        await asyncio.wait_for(me.task, timeout=2)
        assert me.names() == ["fenced", "lost"]
        assert me.ownership.state is OwnershipState.LOST
        assert (await store.read()).holder == holder("next", "r2")

    run(scenario)


def test_a_renewal_whose_reply_was_lost_keeps_the_lease():
    async def scenario():
        lease = FlakyLease(InMemoryLease())
        me = await Serving(lease, holder("me")).start()

        lease.lose_next_update_reply = True
        await asyncio.sleep(TIMING.lease_seconds)

        assert me.names() == []
        assert me.ownership.state is OwnershipState.SERVING
        assert (await lease.read()).holder == holder("me")
        await me.stop()
        assert await lease.read() is None

    run(scenario)


def test_a_deleted_lease_is_taken_again_by_its_engine():
    async def scenario():
        lease = InMemoryLease()
        me = await Serving(lease, holder("me")).start()

        await lease.delete((await lease.read()).revision)
        await asyncio.sleep(TIMING.lease_seconds / 2)

        assert me.names() == []
        assert (await lease.read()).holder == holder("me")
        await me.stop()

    run(scenario)


def test_timing_rejects_non_positive_periods():
    with pytest.raises(ValueError):
        OwnershipTiming(lease_seconds=0)
    with pytest.raises(ValueError):
        OwnershipTiming(standby_timeout_seconds=-1)


# --- deploys need shared backends ------------------------------------------------------


def test_a_rollout_with_shared_backends_may_hand_over():
    require_shared_backends(holder("me", "v2"), {})


def test_an_engine_without_a_rollout_may_keep_data_locally():
    require_shared_backends(holder("me"), {"document": "SQLite at a.db"})


def test_a_rollout_with_local_backends_is_refused_naming_each_one():
    local = {"document": "SQLite at a.db", "kv": "this process"}

    with pytest.raises(LocalBackendsCannotHandOver) as raised:
        require_shared_backends(holder("me", "v2"), local)

    message = str(raised.value)
    assert "v2" in message
    assert "document: SQLite at a.db" in message
    assert "kv: this process" in message
    assert raised.value.local_backends == local
