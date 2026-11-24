"""Ports of the platform's drives (Platform Settings > Drives).

A drive is where files are stored: today one, the File System (the engine's
object storage); later others (Google Drive, S3 buckets...). Each is described
from the engine's configuration (type, provider, where in the storage) and
probed with one small read. A description never carries a credential: access
keys, secrets and tokens stay in the configuration.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal

DriveStatus = Literal["reachable", "unreachable"]


@dataclass(frozen=True)
class DriveLocation:
    """Where a drive keeps its files, one part at a time (``bucket``: ``abi``)."""

    label: str
    value: str


@dataclass(frozen=True)
class DriveDescription:
    """What the configuration says of a drive, no credential in it."""

    id: str
    name: str
    type: str
    provider: str
    # The configured adapter (``s3``, ``fs``...).
    adapter: str
    location: tuple[DriveLocation, ...] = ()


@dataclass(frozen=True)
class Drive:
    """A row of Platform Settings > Drives: its description and whether it answers."""

    description: DriveDescription
    status: DriveStatus


class DriveSource(ABC):
    """One drive of the platform."""

    @abstractmethod
    def describe(self) -> DriveDescription:
        """The drive as configured: never a credential."""

    @abstractmethod
    def probe(self) -> None:
        """One small read against the storage (blocking): returns when it answers,
        raises when it does not."""
