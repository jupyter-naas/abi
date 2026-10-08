"""The engine ownership lease: who serves the kernel services on a NATS account.

See docs/adr/20261006_single-serving-engine.md.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


class LeaseConflict(Exception):
    """The lease is not at the expected revision: another engine wrote it."""


class LeaseTaken(LeaseConflict):
    """``create`` found the lease already held."""


@dataclass(frozen=True)
class Holder:
    """The engine holding (or claiming) the lease."""

    instance_id: str
    host: str
    pid: int
    version: str
    rollout_id: str
    started_at: str

    def describe(self) -> str:
        return (
            f"{self.instance_id or 'unknown'} on {self.host or 'unknown host'} "
            f"(pid {self.pid}, version {self.version or 'unknown'}, "
            f"rollout {self.rollout_id or 'none'}, since {self.started_at or 'unknown'})"
        )


@dataclass(frozen=True)
class LeaseRecord:
    holder: Holder
    revision: int


class EngineLeasePort(ABC):
    """One record, written only by compare-and-swap on its revision.

    Revisions are positive and only move forward; an absent record has
    revision 0.
    """

    @abstractmethod
    async def read(self) -> LeaseRecord | None:
        """The current record, or None when the lease is free."""

    @abstractmethod
    async def create(self, holder: Holder) -> int:
        """Take a free lease; returns its revision. Raises ``LeaseTaken``."""

    @abstractmethod
    async def update(self, holder: Holder, revision: int) -> int:
        """Rewrite the record at ``revision``; returns the new revision.

        Always moves the revision forward, even for the same holder: that is
        how a holder shows it is alive. Raises ``LeaseConflict`` when the
        record is at another revision or absent.
        """

    @abstractmethod
    async def delete(self, revision: int) -> None:
        """Free the lease at ``revision``. Raises ``LeaseConflict`` otherwise."""

    @abstractmethod
    async def wait_for_change(
        self, revision: int, timeout: float
    ) -> LeaseRecord | None:
        """Wait until the lease is no longer at ``revision`` (0: absent), at most
        ``timeout`` seconds; returns the record as it then is."""
