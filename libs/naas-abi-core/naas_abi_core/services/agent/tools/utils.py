from __future__ import annotations

from langchain_core.language_models import BaseChatModel
from langchain_core.tools import tool
from naas_abi_core import logger


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
