"""Whether this engine may serve the kernel services: claim, stand by, keep, release.

The state machine of docs/adr/20261006_single-serving-engine.md, over any
``EngineLeasePort``. Expiry is observed, never computed from timestamps: an
engine is gone when its lease's revision has not moved for a full lease period
on the observer's own clock, so clocks are never compared across hosts.

A serving engine renews every quarter period and fences itself (stops serving)
after half a period without a renewal, so it has stopped before any observer
can conclude it is gone.
"""

from __future__ import annotations

import asyncio
import math
from collections.abc import Awaitable, Callable, Mapping
from dataclasses import dataclass
from enum import Enum

from naas_abi_core import logger
from naas_abi_core.engine.ownership.ownership_ports import (
    EngineLeasePort,
    Holder,
    LeaseConflict,
    LeaseRecord,
    LeaseTaken,
)

Callback = Callable[[], Awaitable[None]]


class Claim(Enum):
    SERVING = "serving"
    STANDBY = "standby"


class OwnershipState(Enum):
    IDLE = "idle"
    STANDBY = "standby"
    SERVING = "serving"
    # Holds the lease as far as it knows, but could not renew it: serves nothing.
    FENCED = "fenced"
    # Another engine took the lease.
    LOST = "lost"
    RELEASED = "released"


class OwnershipError(RuntimeError):
    pass


class EngineAlreadyServing(OwnershipError):
    def __init__(self, holder: Holder):
        super().__init__(
            "Another engine already serves this NATS account: "
            f"{holder.describe()}. Stop it first, or deploy with a new "
            "ABI_ROLLOUT_ID to take over without downtime."
        )
        self.holder = holder


class StandbyTimedOut(OwnershipError):
    pass


class LocalBackendsCannotHandOver(OwnershipError):
    def __init__(self, rollout_id: str, local_backends: Mapping[str, str]):
        listed = "; ".join(
            f"{name}: {where}" for name, where in sorted(local_backends.items())
        )
        super().__init__(
            f"Rollout {rollout_id} hands over without downtime, which needs every "
            f"service on a shared backend, but these keep their data on this host: "
            f"{listed}. Configure shared backends, or deploy without ABI_ROLLOUT_ID "
            "and stop the serving engine first."
        )
        self.local_backends = dict(local_backends)


def require_shared_backends(me: Holder, local_backends: Mapping[str, str]) -> None:
    """A deploy (rollout id) hands over to a running engine, so no service it
    owns may keep its data on this host (``local_backends``: service -> where)."""
    if me.rollout_id and local_backends:
        raise LocalBackendsCannotHandOver(me.rollout_id, local_backends)


@dataclass(frozen=True)
class OwnershipTiming:
    lease_seconds: float = 20.0
    standby_timeout_seconds: float = 900.0

    def __post_init__(self) -> None:
        for name in ("lease_seconds", "standby_timeout_seconds"):
            value = getattr(self, name)
            if not math.isfinite(value) or value <= 0:
                raise ValueError(f"{name} must be a positive number of seconds")

    @property
    def renew_seconds(self) -> float:
        return self.lease_seconds / 4

    @property
    def fence_seconds(self) -> float:
        return self.lease_seconds / 2


async def _notify(callback: Callback | None) -> None:
    if callback is not None:
        await callback()


class EngineOwnership:
    def __init__(
        self,
        lease: EngineLeasePort,
        me: Holder,
        timing: OwnershipTiming | None = None,
    ):
        self.lease, self.me = lease, me
        self.timing = timing or OwnershipTiming()
        self.state = OwnershipState.IDLE
        self._revision = 0
        self._seen: LeaseRecord | None = None
        self._writes = asyncio.Lock()
        self._stop = asyncio.Event()

    # --- starting --------------------------------------------------------------------------

    def _may_stand_by(self, holder: Holder) -> bool:
        """Only a deploy (a rollout id) other than the holder's waits for it."""
        return bool(self.me.rollout_id) and holder.rollout_id != self.me.rollout_id

    async def _take(self, record: LeaseRecord | None) -> bool:
        """Take the lease from ``record`` (None: free); False when someone wrote first."""
        try:
            if record is None:
                revision = await self.lease.create(self.me)
            else:
                revision = await self.lease.update(self.me, record.revision)
        except LeaseConflict:
            return False
        self._revision = revision
        self.state = OwnershipState.SERVING
        if record is not None:
            logger.warning(
                f"Took over the engine lease from {record.holder.describe()}: "
                f"no renewal for {self.timing.lease_seconds:g}s"
            )
        return True

    async def claim(self) -> Claim:
        """Serve now, stand by for a handover, or raise ``EngineAlreadyServing``.

        A holder that is not renewing is gone after one lease period, and its
        lease is taken over. A live holder blocks a new engine, unless the new
        one belongs to another rollout: then it stands by.
        """
        record = await self.lease.read()
        while True:
            if record is None:
                if await self._take(None):
                    return Claim.SERVING
                record = await self.lease.read()
                continue
            if self._may_stand_by(record.holder):
                self._seen = record
                self.state = OwnershipState.STANDBY
                return Claim.STANDBY
            changed = await self.lease.wait_for_change(
                record.revision, self.timing.lease_seconds
            )
            if changed is None:
                record = None  # released meanwhile
            elif changed.revision != record.revision:
                if changed.holder == record.holder:
                    raise EngineAlreadyServing(record.holder)  # it renewed: alive
                record = changed  # another engine took it: decide again
            elif await self._take(record):  # silent for a full period: gone
                return Claim.SERVING
            else:
                record = await self.lease.read()

    async def wait_for_lease(self) -> None:
        """From standby, serve once the holder releases or is gone.

        Raises ``StandbyTimedOut`` after ``standby_timeout_seconds``, and
        ``EngineAlreadyServing`` if an engine of this rollout serves first.
        """
        if self.state is not OwnershipState.STANDBY:
            raise OwnershipError("wait_for_lease() needs a standby claim")
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self.timing.standby_timeout_seconds
        record, silent_since = self._seen, loop.time()
        while True:
            if record is None:
                if await self._take(None):
                    return
                record, silent_since = await self.lease.read(), loop.time()
                continue
            if record.holder.rollout_id == self.me.rollout_id:
                self.state = OwnershipState.IDLE
                raise EngineAlreadyServing(record.holder)
            now = loop.time()
            if now - silent_since >= self.timing.lease_seconds:
                if await self._take(record):
                    return
                record, silent_since = await self.lease.read(), loop.time()
                continue
            if now >= deadline:
                self.state = OwnershipState.IDLE
                raise StandbyTimedOut(
                    "No handover within "
                    f"{self.timing.standby_timeout_seconds:g}s: the engine lease is "
                    f"still held by {record.holder.describe()}"
                )
            changed = await self.lease.wait_for_change(
                record.revision,
                min(self.timing.lease_seconds - (now - silent_since), deadline - now),
            )
            if changed is None:
                record = None
            elif changed.revision != record.revision:
                record, silent_since = changed, loop.time()

    # --- serving ---------------------------------------------------------------------------

    async def _renew(self) -> bool:
        """True while the lease is ours; False once another engine holds it."""
        try:
            self._revision = await self.lease.update(self.me, self._revision)
            return True
        except LeaseConflict:
            pass
        current = await self.lease.read()
        if current is None:  # deleted under us
            try:
                self._revision = await self.lease.create(self.me)
                return True
            except LeaseTaken:
                return False
        if current.holder == self.me:
            # An earlier renewal committed but its reply was lost.
            self._revision = await self.lease.update(self.me, current.revision)
            return True
        return False

    async def keep(
        self,
        *,
        on_fenced: Callback | None = None,
        on_restored: Callback | None = None,
        on_lost: Callback | None = None,
    ) -> None:
        """Renew until released or lost.

        ``on_fenced`` runs when renewals have failed for half a lease period:
        stop serving. ``on_restored`` runs when a renewal succeeds again while
        the lease is still ours: serve again. ``on_lost`` runs once another
        engine holds the lease: this engine must not serve again.
        """
        loop = asyncio.get_running_loop()
        renewed_at = loop.time()
        while self.state in (OwnershipState.SERVING, OwnershipState.FENCED):
            try:
                await asyncio.wait_for(self._stop.wait(), self.timing.renew_seconds)
                return
            except TimeoutError:
                pass
            attempt = loop.time()
            try:
                async with self._writes:
                    if self.state not in (
                        OwnershipState.SERVING,
                        OwnershipState.FENCED,
                    ):
                        return
                    # Bounded: a hung call must not delay fencing.
                    ours: bool | None = await asyncio.wait_for(
                        self._renew(), self.timing.renew_seconds
                    )
            except Exception as exc:  # noqa: BLE001 - the broker may be unreachable
                logger.warning(f"Could not renew the engine lease: {exc!r}")
                ours = None
            if ours is True:
                renewed_at = attempt
                if self.state is OwnershipState.FENCED:
                    self.state = OwnershipState.SERVING
                    logger.warning("Engine lease renewed again: serving")
                    await _notify(on_restored)
            elif ours is False:
                self.state = OwnershipState.LOST
                current = await self._read_quietly()
                logger.error(
                    "Another engine took the engine lease: "
                    f"{current.holder.describe() if current else 'unknown'}"
                )
                await _notify(on_lost)
                return
            if (
                self.state is OwnershipState.SERVING
                and loop.time() - renewed_at >= self.timing.fence_seconds
            ):
                self.state = OwnershipState.FENCED
                logger.error(
                    "Engine lease not renewed for "
                    f"{self.timing.fence_seconds:g}s: stopped serving"
                )
                await _notify(on_fenced)

    async def _read_quietly(self) -> LeaseRecord | None:
        try:
            return await self.lease.read()
        except Exception:  # noqa: BLE001 - only used for a log line
            return None

    async def release(self) -> None:
        """Stop renewing and free the lease if it is still ours."""
        self._stop.set()
        async with self._writes:
            held = self.state in (OwnershipState.SERVING, OwnershipState.FENCED)
            self.state = OwnershipState.RELEASED
            if not held:
                return
            try:
                await asyncio.wait_for(
                    self.lease.delete(self._revision), self.timing.renew_seconds
                )
            except LeaseConflict:
                pass  # another engine holds it now: not ours to free
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    f"Could not release the engine lease ({exc!r}); "
                    f"it frees itself after {self.timing.lease_seconds:g}s"
                )
