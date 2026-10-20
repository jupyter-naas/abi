"""Manual triggers and cancels over NATS, through the SDK's JobProxy and JobRun.

A trigger is a JetStream message on the job's trigger subject (the host's
consumer turns it into a run); the run id is its stream sequence. A cancel is a
core-NATS message the hosts of the module listen to; it is cooperative.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import SourceUnavailable

TIMEOUT_SECONDS = 10.0


def _unavailable(exc: BaseException) -> SourceUnavailable:
    code = getattr(exc, "code", "") or type(exc).__name__
    return SourceUnavailable("jobs", f"{code}: {exc}" if str(exc) else code)


class NatsJobControl:
    def __init__(
        self, transport: Callable[[], Any], project: str, *, timeout: float = TIMEOUT_SECONDS
    ) -> None:
        self._transport = transport
        self.project = project
        self._timeout = timeout

    async def trigger(self, module_id: str, job: str, payload: dict[str, Any]) -> str:
        from naas_abi_sdk.jobs import JobDescriptor, JobProxy

        proxy = JobProxy(self._transport(), self.project, module_id, JobDescriptor(job))
        try:
            run = await asyncio.wait_for(proxy.trigger(payload), self._timeout)
        except Exception as exc:  # noqa: BLE001 - no broker, no stream, timeouts
            raise _unavailable(exc) from exc
        return run.run_id

    async def cancel(self, module_id: str, job: str, run_id: str) -> None:
        from naas_abi_sdk.jobs import JobRun

        try:
            await asyncio.wait_for(
                JobRun(self._transport(), self.project, module_id, job, run_id).cancel(),
                self._timeout,
            )
        except Exception as exc:  # noqa: BLE001
            raise _unavailable(exc) from exc
