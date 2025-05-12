from src.core.apps.terminal_agent.terminal_style import (
    clear_screen,
    print_welcome_message,
    print_divider,
    get_user_input,
    print_tool_usage,
    print_agent_response,
    print_tool_response,
    print_image,
)
from abi.services.agent.Agent import Agent
from langgraph.types import Command
from langchain_core.messages import ToolMessage
from typing import Union
# import json

def on_tool_response(message: Union[str, Command, dict, ToolMessage]):
    try:
        message_content = ''
        if isinstance(message, str):
            message_content = message
        elif isinstance(message, dict) and 'content' in message:
            message_content = message['content']
        elif isinstance(message, Command):
            message_content = message.content
        elif isinstance(message, ToolMessage):
            message_content = message.content
        else:
            print('Unknown message type:')
            print(type(message))
            message_content = message

        # This would nicely display JSON but it takes a lot of screen space
        # try:
        #     message_content = json.dumps(json.loads(message_content), indent=4)
        # except:
        #     pass

        print_tool_response(message_content)
        
        # Check if the message contains a path to an image file
        if isinstance(message_content, str):
            # Look for image file paths in the message
            words = message_content.split(" ")
            for word in words:
                if any(
                    word.lower().endswith(ext)
                    for ext in [".png", ".jpg", ".jpeg", ".gif"]
                ):
                    print_image(word)
    except Exception as e:
        print(e)


def run_agent(agent: Agent):
    clear_screen()
    print_welcome_message()
    print_divider()

    while True:
        user_input = get_user_input()

        if user_input == "exit":
            return
        elif user_input == "help":
            print_welcome_message()
            continue
        elif user_input == "reset":
            agent.reset()
            clear_screen()
            continue

        print_divider()
        response = agent.invoke(user_input)
        print_agent_response(response)
        print_divider()


def generic_run_agent(agent_class: str = None):
    """Run an agent dynamically loaded from the src/modules directory.

    This method provides a generic way to run any agent that is loaded from the modules
    directory, eliminating the need to create individual run functions for each agent.
    The agents are automatically discovered and loaded through the module system.

    Args:
        agent_class (str, optional): The class name of the agent to run. If None, will
            print an error message. The class name should match exactly with the agent's
            class name in the modules.

    Example:
        >>> generic_run_agent("SupervisorAssistant")  # Runs the SupervisorAssistant agent
        >>> generic_run_agent("ContentAssistant")     # Runs the ContentAssistant agent

    Note:
        This replaces the need for individual run_*_agent() functions by dynamically
        finding and running the requested agent from the loaded modules. The agent
        must be properly registered in a module under src/modules for this to work.
    """
    from src.__modules__ import get_modules

    if agent_class is None:
        print(
            "No agent class provided. Please set the AGENT_CLASS environment variable."
        )
        return

    for module in get_modules():
        for agent in module.agents:
            print(agent.__class__.__name__)
            if agent.__class__.__name__ == agent_class:
                agent.on_tool_usage(
                    lambda message: print_tool_usage(message)
                )
                agent.on_tool_response(on_tool_response)
                run_agent(agent)
                return

    print(f"Agent {agent_class} not found")


if __name__ == "__main__":
    import sys

    # Get the function name from command line argument
    if len(sys.argv) > 1:
        function_name = sys.argv[1]
        if function_name in globals():
            globals()[function_name](*sys.argv[2:])
        else:
            print(f"Function {function_name} not found")
    else:
        print("Please specify a function to run")
