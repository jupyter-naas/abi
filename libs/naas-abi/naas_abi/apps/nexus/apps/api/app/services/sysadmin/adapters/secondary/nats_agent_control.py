"""Cancelling a remote agent run over NATS, on the instance that owns it.

The request goes to ``agent_subject(project, sa, owner, agent, "cancel")``, the
owner's service account read from discovery, with the
API's service token; the agent host lets a platform administrator (discovery's
admin identities) cancel any caller's run. Cancelling is cooperative: the run
stops at its next step and records CANCELLED.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.sysadmin.agents import AgentRun
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import SourceUnavailable

TIMEOUT_SECONDS = 10.0


class NatsAgentControl:
    def __init__(
        self, transport: Callable[[], Any], project: str, *, timeout: float = TIMEOUT_SECONDS
    ) -> None:
        self._transport = transport
        self.project = project
        self._timeout = timeout

    async def _service_account(self, run: AgentRun) -> str:
        """The owner instance's service account: its subjects carry it."""
        from naas_abi_sdk.discovery import DiscoveryClient

        discovery = DiscoveryClient(self._transport(), self.project)
        after = ""
        while True:
            instances, after = await asyncio.wait_for(
                discovery.list_modules(after_instance_id=after), self._timeout
            )
            for instance in instances:
                if instance.instance_id == run.owner:
                    return instance.service_account
            if not after:
                return ""

    async def cancel(self, run: AgentRun) -> None:
        from naas_abi_proto.agent.v1 import agent_pb2 as pb
        from naas_abi_sdk.agent import agent_subject
        from nats.errors import NoRespondersError

        try:
            service_account = await self._service_account(run)
        except Exception as exc:  # noqa: BLE001 - discovery down, timeouts, refusals
            code = getattr(exc, "code", "") or type(exc).__name__
            raise SourceUnavailable(
                "agents", f"discovery could not name the run's owner: {code}"
            ) from exc
        subject = agent_subject(self.project, service_account, run.owner, run.agent, "cancel")
        request = pb.CancelRequest(invocation_id=run.invocation_id, output_format=2)
        try:
            await asyncio.wait_for(
                self._transport().call(subject, request, pb.CancelResponse, instance_id=run.owner),
                self._timeout,
            )
        except NoRespondersError as exc:
            raise SourceUnavailable(
                "agents",
                f"the run's owner instance {run.owner} is not running; its claim needs reconciling",
            ) from exc
        except Exception as exc:  # noqa: BLE001 - broker errors, timeouts, refusals
            code = getattr(exc, "code", "") or type(exc).__name__
            raise SourceUnavailable("agents", f"{code}: {exc}" if str(exc) else code) from exc
