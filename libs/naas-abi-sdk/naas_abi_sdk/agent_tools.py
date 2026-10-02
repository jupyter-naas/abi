"""Optional LangChain adapter; import only when as_tools() is requested."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from langchain_core.runnables import RunnableConfig
from langchain_core.tools import StructuredTool

from naas_abi_sdk.agent import AgentState

if TYPE_CHECKING:
    from naas_abi_sdk.agent import AgentProxy


def agent_tools(agent: AgentProxy) -> list[StructuredTool]:
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    async def invoke(prompt: str, config: RunnableConfig) -> str:
        thread_id = config.get("configurable", {}).get(
            "thread_id", agent.state.thread_id
        )
        scoped = agent.duplicate(agent_shared_state=AgentState(str(thread_id)))
        return await scoped.invoke(prompt)

    def sync_invoke(prompt: str, config: RunnableConfig) -> str:
        if loop is None or not loop.is_running():
            raise RuntimeError(
                "Create remote tools inside the running module; use ainvoke for async callers"
            )
        try:
            current = asyncio.get_running_loop()
        except RuntimeError:
            current = None
        if current is loop:
            raise RuntimeError("Use tool.ainvoke on the module event loop")
        return asyncio.run_coroutine_threadsafe(invoke(prompt, config), loop).result()

    return [
        StructuredTool.from_function(
            func=sync_invoke,
            coroutine=invoke,
            name=agent.name,
            description=agent.description or agent.name,
        )
    ]
