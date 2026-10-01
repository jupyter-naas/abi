"""Agents published by remote modules (NATS discovery, ``agent.invoke.v1``).

Nexus lists them next to in-process agents and streams chat turns to them.
Rows for them carry ``provider == REMOTE_PROVIDER`` and ``class_name == key``.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Protocol

REMOTE_PROVIDER = "remote"
# The SDK AgentHost rejects larger prompts (naas_abi_sdk.agent_host).
MAX_PROMPT_BYTES = 64 * 1024


class RemoteAgentUnavailable(Exception):
    """The agent is not published by any READY module, or its run failed."""

    def __init__(self, key: str, reason: str) -> None:
        super().__init__(f"Remote agent {key} unavailable: {reason}")
        self.key, self.reason = key, reason


@dataclass(frozen=True)
class RemoteAgent:
    module_id: str
    name: str
    description: str = ""

    @property
    def key(self) -> str:
        """``<module_id>/<agent>``: what workspace ``agents:`` refs resolve against."""
        return f"{self.module_id}/{self.name}"


def split_key(key: str) -> tuple[str, str]:
    module_id, _, name = key.rpartition("/")
    if not module_id or not name:
        raise ValueError(f"Not a remote agent key: {key!r}")
    return module_id, name


class RemoteAgentDirectory(Protocol):
    async def list_agents(self) -> list[RemoteAgent]:
        """Agents currently invocable (one entry per module/agent, any replica count)."""
        ...

    def stream(
        self, key: str, prompt: str, *, thread_id: str, invocation_id: str | None = None
    ) -> AsyncIterator[dict[str, str]]:
        """Run one turn; yields ``{"event", "data"}`` like core ``Agent.stream_invoke``.

        Raises RemoteAgentUnavailable when the agent cannot be reached or its run fails.
        """
        ...
