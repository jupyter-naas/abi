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
import time
import threading
from datetime import datetime
from pathlib import Path
from abi import logger

# Global variable to track active agent for context-aware conversations
current_active_agent = None
conversation_file = None

# Fixed width for consistent conversation logs (matches typical wide terminal)
TERMINAL_WIDTH = 77  # Matches the separator length from the user's example

def init_conversation_file():
    """Initialize a new conversation file with timestamp"""
    global conversation_file
    
    # Create timestamp in format YYYYMMDDTHHMMSS
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    
    # Create directory structure
    conversation_dir = Path("storage/datastore/interfaces/terminal_agent")
    conversation_dir.mkdir(parents=True, exist_ok=True)
    
    # Create conversation file path
    conversation_file = conversation_dir / f"{timestamp}.txt"
    
    # Initialize file with header
    with open(conversation_file, 'w', encoding='utf-8') as f:
        f.write(f"# ABI Terminal Conversation - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"# Session started at: {timestamp}\n")
        f.write("=" * 80 + "\n\n")
    
    logger.info(f"💾 Conversation logging to: {conversation_file}")
    return conversation_file

def save_to_conversation(line: str):
    """Save exactly what appears in terminal to the conversation file"""
    global conversation_file
    
    if conversation_file is None:
        return
    
    try:
        with open(conversation_file, 'a', encoding='utf-8') as f:
            f.write(line + "\n")
    except Exception as e:
        # Print error to terminal
        print(f"⚠️ Error saving to conversation file: {e}")
        # Try to log the error itself if possible
        try:
            with open(conversation_file, 'a', encoding='utf-8') as f:
                f.write(f"⚠️ LOGGING ERROR: {e}\n")
        except Exception:
            pass  # If we can't log the error, give up

def get_input_with_placeholder(prompt="> ", placeholder="Send a message (/? for help)"):
    """Get user input with a placeholder that disappears when typing starts"""
    
    # Check if input is piped (not interactive terminal)
    if not sys.stdin.isatty():
        # For piped input, use simple input() without fancy terminal handling
        print(f"\n{prompt}", end="", flush=True)
        try:
            return input()
        except: # noqa: E722
            return "/bye"
    
    # Interactive terminal - use fancy placeholder logic
    print(f"\n{prompt}", end="", flush=True)
    
    # Show placeholder in grey
    print(f"\033[90m{placeholder}\033[0m", end="", flush=True)
    
    # Move cursor back to start of placeholder
    print(f"\033[{len(placeholder)}D", end="", flush=True)
    
    user_input = ""
    placeholder_cleared = False
    
    old_settings = termios.tcgetattr(sys.stdin)

    
    try:
        tty.setraw(sys.stdin.fileno())
        
        while True:
            char = sys.stdin.read(1)
            
            # Handle Enter key
            if ord(char) == 13:  # Enter
                # Clear the current line before returning
                print("\r\033[2K", end="", flush=True)
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
        error_msg = f"⚠️ Tool Response Error: {e}"
        print(error_msg)
        # Log the error to conversation file
        save_to_conversation(error_msg)


def on_ai_message(message: Any, agent_name) -> None:
    global current_active_agent
    
    if len(message.content) == 0:
        return
    
    # Update active agent when an agent responds
    current_active_agent = agent_name
    
    print("\r" + " " * 15 + "\r", end="", flush=True)
    
    from rich.markdown import Markdown
    
    # Filter out think tags and their content
    think_content = re.findall(r'<think>.*?</think>', message.content, flags=re.DOTALL)
    
    # Prepare thoughts section for both display and logging
    thoughts_for_log = ""
    if len(think_content) > 0:
        console.print('Thoughts:', style="grey66")
        thoughts_for_log += "Thoughts:      \n\n"
        for think in think_content:
            think_text = think.replace('<think>', '').replace('</think>', '').strip()
            console.print(think_text, style="grey66")
            thoughts_for_log += think_text + "\n"
        thoughts_for_log += "\n"  # Extra line after thoughts
    
    content = re.sub(r'<think>.*?</think>', '', message.content, flags=re.DOTALL).strip()

    # Print agent name dynamically using the real intent_target
    
    # Use the actual agent name from intent_target, with color coding for readability
    if "gemini" in agent_name.lower() or "google" in agent_name.lower():
        color = "bold blue"
    elif "supervisor" in agent_name.lower() or "abi" in agent_name.lower():
        color = "bold green"
    elif "ontology" in agent_name.lower():
        color = "bold cyan"
    elif "support" in agent_name.lower():
        color = "bold yellow"
    else:
        color = "bold magenta"
    
    # Format exactly as it appears in terminal
    agent_message_line = f"{agent_name}: {content}"
    
    # Display the real agent name
    console.print(f"{agent_name}:", style=color, end=" ")
    
    md = Markdown(content)
    console.print(md, style="bright_white")
    console.print("─" * console.width, style="dim")
    print()  # Add spacing after separator
    
    # Save exact terminal format to conversation file (with fixed width) including thoughts
    if thoughts_for_log:
        save_to_conversation(thoughts_for_log)
    save_to_conversation(agent_message_line)
    save_to_conversation("─" * TERMINAL_WIDTH)
    save_to_conversation("")  # Empty line
    
def run_agent(agent: Agent):
    global current_active_agent
    
    # Initialize conversation logging
    init_conversation_file()
    
    # Show greeting when truly ready for input - instant like responses
    greeting_line = "Abi: Hello, World!"
    
    console.print("Abi:", style="bold green", end=" ")
    console.print("Hello, World!", style="bright_white")
    console.print("─" * console.width, style="dim")
    print()  # Add spacing after separator
    
    # Save exact terminal output to conversation file (with fixed width)
    save_to_conversation(greeting_line)
    save_to_conversation("─" * TERMINAL_WIDTH)
    save_to_conversation("")  # Empty line
    
    # Available agents for mention suggestions (cloud + local)
    available_agents = [
        # Cloud agents
        "gemini", "claude", "mistral", "chatgpt", "perplexity", "llama",
        # Local agents (privacy-focused)
        "qwen", "deepseek", "gemma"
    ]
    # Map from mention names to actual agent names
    agent_name_mapping = {
        # Cloud agents
        "gemini": "Gemini",
        "claude": "Claude", 
        "mistral": "Mistral",
        "chatgpt": "ChatGPT",
        "perplexity": "Perplexity",
        "llama": "Llama",
        # Local agents
        "qwen": "Qwen",
        "deepseek": "DeepSeek", 
        "gemma": "Gemma"
    }
    
    # Just start chatting naturally - like the screenshot
    while True:
        # Set Abi as active agent after greeting
        current_active_agent = agent.name
        if hasattr(agent.chat_model, 'model_name'):
            model_info = agent.chat_model.model_name
        elif hasattr(agent.chat_model, 'model'):
            model_info = agent.chat_model.model
        else:
            model_info = "unknown"
            
        # Create clean status line showing active agent with model info
        if current_active_agent:
            status_line = f"Active: {current_active_agent} (model: {model_info})"
        else:
            status_line = "No active agent"
        
        # Print the status line before the input prompt
        console.print(status_line, style="dim")
        
        # Save status line to conversation file
        save_to_conversation(status_line)
        save_to_conversation("")  # Empty line for spacing
        
        user_input = get_input_with_placeholder()
        
        # Clean the input and check for exit commands
        clean_input = user_input.strip().lower()
        
        # Skip empty input
        if not user_input.strip():
            continue
        
        # Check for agent switching with @agent syntax
        agent_mention_match = re.search(r'@(\w+)', user_input.lower())
        if agent_mention_match:
            mentioned_agent = agent_mention_match.group(1)
            # Map agent mentions to full names (use the updated agent names)
            agent_mapping = agent_name_mapping
            
            if mentioned_agent in agent_mapping:
                current_active_agent = agent_mapping[mentioned_agent]
                # Remove the @mention from the input and route to agent
                user_input_clean = re.sub(r'@\w+\s*', '', user_input).strip()
                if user_input_clean:
                    # There's additional content, send it to the mentioned agent
                    user_input = f"ask {mentioned_agent} {user_input_clean}"
                else:
                    # Just the mention, initiate conversation with agent
                    user_input = f"I want to talk to {mentioned_agent}"
            else:
                console.print(f"Unknown agent: @{mentioned_agent}", style="red")
                console.print(f"Available agents: {', '.join(['@' + name for name in available_agents])}", style="dim")
                continue
            
        # Display user message with color coding and separator (except for commands)
        if (not clean_input.startswith('/') and 
            clean_input not in ["exit", "quit", "reset"]):
            # Format exactly as it appears in terminal
            user_message_line = f"You: {user_input.strip()}"
            
            # Show formatted message in chat history (same format as Abi)
            console.print("You:", style="bold cyan", end=" ")
            console.print(user_input.strip(), style="bright_white")
            console.print("─" * console.width, style="dim")
            print()  # Add spacing after separator
            
            # Save exact terminal format to conversation file (with fixed width)
            save_to_conversation(user_message_line)
            save_to_conversation("─" * TERMINAL_WIDTH)
            save_to_conversation("")  # Empty line
        
        if clean_input in ["exit", "/exit", "/bye", "quit", "/quit"]:
            # Save session end to conversation file
            save_to_conversation("")  # Empty line
            save_to_conversation("# Session ended by user")
            print(f"\n👋 See you later! Conversation saved to: {conversation_file}")
            return
        elif clean_input in ["reset", "/reset"]:
            agent.reset()
            print("🔄 Starting fresh...")
            continue
        elif clean_input == "/?":
            print("\n📋 Available Commands:")
            print("  /? - Show this help")
            print("  /reset - Start fresh conversation") 
            print("  /bye or /exit - End conversation")
            print("\n🤖 Available AI Agents:")
            print("  Cloud Agents:")
            cloud_agents = ["@gemini", "@claude", "@mistral", "@chatgpt", "@perplexity", "@llama"]
            print(f"    {' '.join(cloud_agents)}")
            print("  Local Agents (Privacy-focused):")
            local_agents = ["@qwen", "@deepseek", "@gemma"]
            print(f"    {' '.join(local_agents)}")
            print("\n💡 Usage: Type @agent or 'ask agent' to switch agents")
            print("   Example: '@qwen help me code' or 'ask deepseek solve this math problem'")
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
        
        # Update the agent's shared state with current active agent info
        if hasattr(agent, '_state') and hasattr(agent._state, 'set_current_active_agent'):
            agent._state.set_current_active_agent(current_active_agent)
        
        # Get the response while animation runs with error handling
        try:
            agent.invoke(user_input)
        except Exception as e:
            # Stop the animation first
            loading = False
            loader_thread.join()
            
            # Clear the loading line
            print("\r" + " " * 15 + "\r", end="", flush=True)
            
            # Display and log the error
            error_msg = f"❌ Agent Error: {e}"
            console.print(error_msg, style="bold red")
            save_to_conversation(error_msg)
            
            # Log the full traceback for debugging
            import traceback
            traceback_msg = f"Full traceback:\n{traceback.format_exc()}"
            console.print(traceback_msg, style="dim red")
            save_to_conversation(traceback_msg)
            save_to_conversation("─" * TERMINAL_WIDTH)
            save_to_conversation("")  # Empty line
            return  # Continue conversation instead of crashing
        
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


def load_agent(agent_class: str) -> Agent | None:
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
                
            
                return agent
        
    return None

def list_available_agents():
    from src import modules
    print("\nAvailable agents:\n")
    agents = []
    for module in modules:
        for agent in module.agents:
            agents.append(agent.__class__.__name__)
    
    # Sort the agents alphabetically
    agents.sort()
    
    # Print the agents
    for agent in agents:
        print(f"  - {agent}")

class ConsoleLoader:

    
    def stop(self):
        self.loading = False
        self.loader_thread.join()
        
        # Clear the loading line
        print("\r" + " " * 20 + "\r", end="", flush=True)
    
    def start(self, message: str):
        # Matrix-style startup animation
        self.loading = True
        
        def startup_loader():
            i = 0
            while self.loading:
                dots_count = i % 4  # 0, 1, 2, 3, then repeat
                if dots_count == 0:
                    dots = "   "  # No dots, just spaces
                else:
                    dots = "." * dots_count + " " * (3 - dots_count)  # Pad to 3 char width
                print(f"\r\033[92m{message}{dots}\033[0m", end="", flush=True)
                time.sleep(0.5)
                i += 1
        
        # Start the animation
        self.loader_thread = threading.Thread(target=startup_loader)
        self.loader_thread.daemon = True  # Make thread die when main thread exits
        self.loader_thread.start()
        
        # Suppress all logging during module loading
        # import logging
        # logging.getLogger().setLevel(logging.CRITICAL)
        # try:
        #     from loguru import logger
        #     logger.remove()
        #     logger.add(lambda x: None)
        # except: # noqa: E722
        #     pass


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
        >>> generic_run_agent("AbiAgent")  # Runs the AbiAgent agent
        >>> generic_run_agent("ContentAssistant")     # Runs the ContentAssistant agent

    Note:
        This replaces the need for individual run_*_agent() functions by dynamically
        finding and running the requested agent from the loaded modules. The agent
        must be properly registered in a module under src/modules for this to work.
    """
    
    console_loader = ConsoleLoader()
    console_loader.start("Loading")
    
    assert agent_class is not None, "Agent class is required"
    
    agent = load_agent(agent_class)
    
    console_loader.stop()
    
    if agent is None:
        print(f"Agent {agent_class} not found")
        list_available_agents()
        
        return
    
    run_agent(agent)


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
