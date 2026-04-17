from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import ToolCall, ToolMessage
from langchain_core.tools import BaseTool, tool
from langgraph.prebuilt import InjectedState
from langgraph.types import Command
from naas_abi_core import logger

if TYPE_CHECKING:
    from naas_abi_core.services.agent.Agent import Agent


def make_handoff_tool(*, agent: Agent, parent_graph: bool = False) -> BaseTool:
    """Create a tool that can return handoff via a Command"""
    tool_name = f"transfer_to_{agent.name}"

    @tool(tool_name)
    def handoff_to_agent(
        # # optionally pass current graph state to the tool (will be ignored by the LLM)
        state: Annotated[dict, InjectedState],
        # optionally pass the current tool call ID (will be ignored by the LLM)
        tool_call: Annotated[ToolCall, ToolCall],
    ):
        """Ask another agent for help."""
        agent_label = " ".join(
            word.capitalize() for word in agent.name.replace("_", " ").split()
        )

        tool_message = ToolMessage(
            content=f"Conversation transferred to {agent_label}",
            name=tool_name,
            tool_call_id=tool_call["id"],
        )

        agent.state.set_current_active_agent(agent.name)

        return Command(
            # navigate to another agent node in the PARENT graph
            goto=agent.name,
            graph=Command.PARENT if parent_graph else None,
            # This is the state update that the agent `agent_name` will see when it is invoked.
            # We're passing agent's FULL internal message history AND adding a tool message to make sure
            # the resulting chat history is valid. See the paragraph above for more information.
            update={"messages": state["messages"] + [tool_message]},
        )

    assert isinstance(handoff_to_agent, BaseTool)

    return handoff_to_agent


def can_bind_tools(chat_model: BaseChatModel) -> bool:
    """Test if the chat model can bind tools by attempting to bind the get_time_date default tool.

    Args:
        chat_model (BaseChatModel): The chat model to test

    Returns:
        bool: True if the model can bind tools, False otherwise
    """
    try:
        # Create the get_time_date tool that's used in default_tools()
        @tool(return_direct=True)
        def get_time_date(timezone: str = "Europe/Paris") -> str:
            """Get the current time and date."""
            from datetime import datetime
            from zoneinfo import ZoneInfo

            return datetime.now(ZoneInfo(timezone)).strftime("%H:%M:%S %Y-%m-%d")

        # Try to bind this single tool to test if the model supports tool binding
        chat_model.bind_tools([get_time_date])

        # If we get here without an exception, the model supports tool binding
        # logger.debug(f"Chat model {type(chat_model).__name__} supports tool calling.")
        return True

    except Exception as e:
        # If binding tools raises an exception, the model doesn't support tools
        logger.debug(
            f"Chat model {type(chat_model).__name__} does not support tool calling: {e}"
        )
        return False
