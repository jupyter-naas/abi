"""How many triggers wait in a job's JetStream consumer (pending, and acked-pending)."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import SourceUnavailable

TIMEOUT_SECONDS = 3.0


class NatsJobQueue:
    def __init__(
        self,
        connect: Callable[[], Awaitable[Any]],
        project: str,
        *,
        timeout: float = TIMEOUT_SECONDS,
    ) -> None:
        self._connect = connect
        self.project = project
        self._timeout = timeout

    async def depth(self, module_id: str, job: str) -> tuple[int, int] | None:
        from naas_abi_sdk.jobs import job_subjects, stream_name
        from nats.js.errors import NotFoundError

        consumer = job_subjects(self.project, module_id, job).consumer
        try:
            nc = await asyncio.wait_for(self._connect(), self._timeout)
            info = await asyncio.wait_for(
                nc.jetstream().consumer_info(stream_name(self.project), consumer), self._timeout
            )
        except NotFoundError:
            # No host has started this job (or the stream does not exist yet).
            return None
        except Exception as exc:  # noqa: BLE001 - no broker, no JetStream, timeouts
            code = getattr(exc, "code", "") or type(exc).__name__
            raise SourceUnavailable("queue", f"{code}: {exc}" if str(exc) else code) from exc
        return int(info.num_pending or 0), int(info.num_ack_pending or 0)
