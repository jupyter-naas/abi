"""Host an SDK Agent in a module: ``module.expose_agent(name, agent.as_handler())``.

Each invocation runs on a duplicate bound to ``InvocationContext.thread_id``,
which AgentHost already scopes per project, module, agent, caller and conversation;
with ``document_memory`` that thread is checkpointed through the Document Service.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import TYPE_CHECKING, Any

from naas_abi_sdk.agents.agent import AgentSharedState

if TYPE_CHECKING:
    from naas_abi_sdk.agent_host import InvocationContext
    from naas_abi_sdk.agents.agent import Agent


def agent_memory_id(module_id: str, agent_name: str, version: int = 1) -> str:
    """Stable checkpoint scope for an agent: same across replicas and restarts."""
    return f"{module_id}.{agent_name}.v{version}"


async def document_memory(documents: Any, agent_id: str) -> Any:
    """``DocumentCheckpointSaver`` over the module's document service, set up."""
    from naas_abi_sdk.langgraph import DocumentCheckpointSaver

    saver = DocumentCheckpointSaver(documents, agent_id=agent_id)
    await saver.setup()
    return saver


class AgentHandler:
    """``agent.invoke.v1`` handler (``invoke`` / ``stream_invoke``) for an Agent."""

    def __init__(self, agent: Agent) -> None:
        self.agent = agent

    def _scoped(self, context: InvocationContext) -> Agent:
        return self.agent.duplicate(
            agent_shared_state=AgentSharedState(thread_id=context.thread_id)
        )

    async def invoke(self, prompt: str, context: InvocationContext) -> str:
        return await self._scoped(context).invoke(prompt)

    async def stream_invoke(
        self, prompt: str, context: InvocationContext
    ) -> AsyncIterator[dict[str, str]]:
        stream = self._scoped(context).stream_invoke(prompt)
        try:
            async for event in stream:
                yield event
                if context.cancelled.is_set():
                    return
        finally:
            await stream.aclose()
