"""The platform's drives (Platform Settings > Drives): each one as configured, and
whether it answers.

Each drive is probed once per listing, in a thread (the storage clients block),
for at most ``timeout`` seconds. A probe that fails or does not answer in time
makes the drive ``unreachable``; what it raised is logged by type only, never its
text, which can quote a credential or an endpoint's signature.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence

from naas_abi.apps.nexus.apps.api.app.services.drives.port import Drive, DriveSource

logger = logging.getLogger(__name__)

PROBE_TIMEOUT_SECONDS = 5.0


class DriveService:
    def __init__(self, sources: Sequence[DriveSource], *, timeout: float = PROBE_TIMEOUT_SECONDS):
        self._sources = tuple(sources)
        self._timeout = timeout

    async def list(self) -> list[Drive]:
        """Every drive, in the order configured, each probed in parallel."""
        return list(await asyncio.gather(*(self._drive(source) for source in self._sources)))

    async def _drive(self, source: DriveSource) -> Drive:
        description = source.describe()
        try:
            await asyncio.wait_for(asyncio.to_thread(source.probe), timeout=self._timeout)
        except Exception as exc:  # noqa: BLE001 - any failure reads as unreachable
            logger.warning("Drive %s is unreachable (%s)", description.id, type(exc).__name__)
            return Drive(description, "unreachable")
        return Drive(description, "reachable")
