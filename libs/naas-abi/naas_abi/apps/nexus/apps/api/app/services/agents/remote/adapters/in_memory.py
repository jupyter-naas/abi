"""In-process RemoteAgentDirectory: the empty directory when NATS discovery is off,
and a test double that answers through plain async callables."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable, Mapping

from naas_abi.apps.nexus.apps.api.app.services.agents.remote.port import (
    RemoteAgent,
    RemoteAgentUnavailable,
)

Answer = Callable[[str, str], Awaitable[str]]


class InMemoryRemoteAgentDirectory:
    def __init__(self, agents: Mapping[RemoteAgent, Answer] | None = None) -> None:
        self.agents = dict(agents or {})

    async def list_agents(self) -> list[RemoteAgent]:
        return list(self.agents)

    async def stream(
        self, key: str, prompt: str, *, thread_id: str, invocation_id: str | None = None
    ) -> AsyncIterator[dict[str, str]]:
        answer = next((fn for agent, fn in self.agents.items() if agent.key == key), None)
        if answer is None:
            raise RemoteAgentUnavailable(key, "not published")
        text = await answer(prompt, thread_id)
        yield {"event": "ai_message", "data": text}
        yield {"event": "message", "data": text}
        yield {"event": "done", "data": "[DONE]"}
