from src.core.apps.terminal_agent.terminal_style import (
    print_tool_usage,
    print_tool_response,
    print_image,
    console,  # Add console import
)
from abi.services.agent.Agent import Agent
from langgraph.types import Command
from langchain_core.messages import ToolMessage
from typing import Union, Optional, Any
import sys
import tty
import termios
import re
# import json

def get_input_with_placeholder(prompt=">>> ", placeholder="Send a message (/? for help)"):
    """Get user input with a placeholder that disappears when typing starts"""
    print(f"\n{prompt}", end="", flush=True)
    
    # Show placeholder in grey
    print(f"\033[90m{placeholder}\033[0m", end="", flush=True)
    
    # Move cursor back to start of placeholder
    print(f"\033[{len(placeholder)}D", end="", flush=True)
    
    user_input = ""
    placeholder_cleared = False
    
    # Get original terminal settings
    old_settings = termios.tcgetattr(sys.stdin)
    
    try:
        tty.setraw(sys.stdin.fileno())
        
        while True:
            char = sys.stdin.read(1)
            
            # Handle Enter key
            if ord(char) == 13:  # Enter
                print()  # New line
                break
                
            # Handle Backspace
            elif ord(char) == 127:  # Backspace
                if user_input:
                    user_input = user_input[:-1]
                    print("\b \b", end="", flush=True)
                    
            # Handle Ctrl+C
            elif ord(char) == 3:  # Ctrl+C
                print("^C")
                raise KeyboardInterrupt
                
            # Handle printable characters
            elif ord(char) >= 32 and ord(char) <= 126:
                # Clear placeholder on first character
                if not placeholder_cleared:
                    # Clear the placeholder text
                    print(f"\033[2K\r{prompt}", end="", flush=True)
                    placeholder_cleared = True
                    
                user_input += char
                print(char, end="", flush=True)
                
    finally:
        # Restore terminal settings
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
    
    return user_input


def on_tool_response(message: Union[str, Command, dict[str, Any], ToolMessage]) -> None:
    try:
        message_content: str = ""
        if isinstance(message, str):
            message_content = message
        elif isinstance(message, dict) and "content" in message:
            message_content = str(message["content"])
        # elif isinstance(message, Command):
        #     message_content = str(message.kwargs.get("content", ""))
        elif isinstance(message, ToolMessage):
            message_content = str(message.content)
        else:
            print("Unknown message type:")
            print(type(message))
            message_content = str(message)

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


def on_ai_message(message: Any, agent_name) -> None:
    if len(message.content) == 0:
        return
    
    print("\r" + " " * 15 + "\r", end="", flush=True)
    
    from rich.markdown import Markdown
    
    # Filter out think tags and their content
    think_content = re.findall(r'<think>.*?</think>', message.content, flags=re.DOTALL)
    
    if len(think_content) > 0:
        console.print('Thoughts:', style="white")
        for think in think_content:
            console.print(think.replace('<think>', '').replace('</think>', ''), style="white")
    
    content = re.sub(r'<think>.*?</think>', '', message.content, flags=re.DOTALL).strip()

    
    md = Markdown('@' + agent_name + ': ' + content)
    console.print(md)
    
def run_agent(agent: Agent):
    # Show greeting when truly ready for input - instant like responses
    print()  # New line
    print("Hello you!")
    print()  # New line after greeting
    
    # Just start chatting naturally - like the screenshot
    while True:
        user_input = get_input_with_placeholder()
        
        # Clean the input and check for exit commands
        clean_input = user_input.strip().lower()
        
        if clean_input in ["exit", "/exit", "/bye", "quit", "/quit"]:
            print("\n👋 See you later!")
            return
        elif clean_input in ["reset", "/reset"]:
            agent.reset()
            print("🔄 Starting fresh...")
            continue
        elif clean_input == "/?":
            print("Available commands:")
            print("  /? - Show this help")
            print("  /reset - Start fresh conversation")
            print("  /bye or /exit - End conversation")
            continue

        # Matrix-style animated loading indicator
        import threading
        import time
        
        # Animation control
        loading = True
        
        def matrix_loader():
            i = 0
            while loading:
                dots_count = i % 4  # 0, 1, 2, 3, then repeat
                if dots_count == 0:
                    dots = "   "  # No dots, just spaces
                else:
                    dots = "." * dots_count + " " * (3 - dots_count)  # Pad to 3 char width
                print(f"\r\033[92mResponding{dots}\033[0m", end="", flush=True)
                time.sleep(0.5)
                i += 1
        
        # Start the animation in a separate thread
        loader_thread = threading.Thread(target=matrix_loader)
        loader_thread.start()
        
        # Get the response while animation runs
        agent.invoke(user_input)
        
        # Stop the animation
        loading = False
        loader_thread.join()
        
        # Clear the loading line properly
        print("\r" + " " * 15 + "\r", end="", flush=True)
        
        # # Convert list response to string if necessary
        # if isinstance(response, list):
        #     response = "\n".join(str(item) for item in response)
        
        # # Filter out think tags and their content
        # response = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL)
        # response = response.strip()
        
        # # Render markdown properly with rich instead of raw typewriter effect
        # from rich.markdown import Markdown
        # md = Markdown(response)
        # console.print(md)


def generic_run_agent(agent_class: Optional[str] = None) -> None:
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
    from src import modules

    if agent_class is None:
        print(
            "No agent class provided. Please set the AGENT_CLASS environment variable."
        )
        return

    for module in modules:
        for agent in module.agents:
            if agent.__class__.__name__ == agent_class:
                agent.on_tool_usage(lambda message: print_tool_usage(message))
                agent.on_tool_response(on_tool_response)
                agent.on_ai_message(on_ai_message)
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
