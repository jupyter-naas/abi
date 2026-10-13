"""RemoteAgentDirectory over NATS discovery and the SDK AgentProxy.

SDK transports are bound to the event loop that created them, so one discovery
client is kept per running loop (uvicorn's, in the API). The SDK is the core
``[nats]`` extra: import it only here, never at module import time of callers.
"""

from __future__ import annotations

import asyncio
import weakref
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.agents.remote.port import (
    MAX_PROMPT_BYTES,
    RemoteAgent,
    RemoteAgentUnavailable,
    split_key,
)

INVOKE_CAPABILITY = "agent.invoke.v1"
CONTRACT_MAJOR = 1


async def open_agent(client: Any, module_id: str, name: str) -> Any:
    from naas_abi_sdk.discovery import ModuleProxy

    return await ModuleProxy(client, module_id).get_agent(name)


class DiscoveryRemoteAgentDirectory:
    def __init__(
        self,
        discovery_factory: Callable[[], Any],
        *,
        open_agent: Callable[[Any, str, str], Awaitable[Any]] = open_agent,
        timeout_seconds: float = 600.0,
    ) -> None:
        self._factory = discovery_factory
        self._open_agent = open_agent
        self._timeout = timeout_seconds
        self._clients: weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, Any] = (
            weakref.WeakKeyDictionary()
        )

    def _client(self) -> Any:
        loop = asyncio.get_running_loop()
        if loop not in self._clients:
            self._clients[loop] = self._factory()
        return self._clients[loop]

    async def list_agents(self) -> list[RemoteAgent]:
        client, found, after = self._client(), {}, ""
        while True:
            instances, after = await client.list_modules(limit=100, after_instance_id=after)
            for instance in instances:
                if instance.status != "READY" or instance.contract_major != CONTRACT_MAJOR:
                    continue
                for agent in instance.agents:
                    if (
                        INVOKE_CAPABILITY in agent.capabilities
                        and agent.contract_major == CONTRACT_MAJOR
                    ):
                        remote = RemoteAgent(instance.module_id, agent.name, agent.description)
                        found.setdefault(remote.key, remote)  # replicas publish identical agents
            if not after:
                return sorted(found.values(), key=lambda a: a.key)

    async def stream(
        self, key: str, prompt: str, *, thread_id: str, invocation_id: str | None = None
    ) -> AsyncIterator[dict[str, str]]:
        from naas_abi_sdk.agent import AgentState, SubmissionUncertain
        from naas_abi_sdk.transport import RPCError

        module_id, name = split_key(key)
        if len(prompt.encode()) > MAX_PROMPT_BYTES:
            raise RemoteAgentUnavailable(key, "prompt exceeds 64 KiB")
        try:
            proxy = await self._open_agent(self._client(), module_id, name)
            scoped = proxy.duplicate(agent_shared_state=AgentState(thread_id))
            handle = await scoped.submit(prompt, invocation_id=invocation_id, stream=True)
        except RPCError as exc:
            raise RemoteAgentUnavailable(key, exc.code) from exc
        except SubmissionUncertain as exc:
            raise RemoteAgentUnavailable(key, "submission uncertain; not retried") from exc

        finished = False
        try:
            async for event in handle.events(timeout=self._timeout):
                yield {"event": str(event["event"]), "data": str(event["data"])}
            finished = True
        except RPCError as exc:
            finished = True  # the run is already terminal
            raise RemoteAgentUnavailable(key, exc.code) from exc
        finally:
            if not finished:
                # Client went away mid-answer: stop the provider instead of letting it run.
                try:
                    await handle.cancel()
                except Exception:  # noqa: BLE001 - best effort, the run may have just ended
                    pass
