# `terminal_agent.main`

## What it is
A terminal chat runner for a `naas_abi_core.services.agent.Agent` that:
- Displays AI and tool output with Rich styling.
- Accepts interactive input with a disappearing placeholder (TTY only).
- Logs the terminal conversation to a timestamped file under `storage/datastore/interfaces/terminal_agent/`.

## Public API
- `init_conversation_file() -> pathlib.Path`
  - Creates a new timestamped conversation log file and writes a header.
- `save_to_conversation(line: str) -> None`
  - Appends a line to the current conversation log file (if initialized).
- `get_input_with_placeholder(prompt: str = "> ", placeholder: str = "Send a message (/? for help)") -> str`
  - Reads user input.
  - Uses raw-terminal key handling for interactive sessions; falls back to `input()` for piped/non-TTY stdin.
- `on_tool_response(message: langchain_core.messages.AnyMessage) -> None`
  - Formats and prints tool responses via `print_tool_response`.
  - Attempts to detect and render image paths (`.png/.jpg/.jpeg/.gif`) via `print_image`.
- `on_ai_message(message: Any, agent_name: str) -> None`
  - Prints an AI message with agent-name color coding.
  - Extracts and displays `<think>...</think>` blocks as “Thoughts:” (and logs them).
  - Logs output with a fixed-width separator.
- `run_agent(agent: naas_abi_core.services.agent.Agent.Agent) -> None`
  - Main interactive loop:
    - Initializes logging.
    - Registers agent hooks: tool usage, tool response, AI messages.
    - Prints a greeting (`"{agent.name}: Hello, World!"`).
    - Repeatedly:
      - Shows active agent/model line (from `agent.state.current_active_agent` and agent list).
      - Reads user input.
      - Handles commands: `/?`, `/reset`, `/bye`, `/exit`, `exit`, `quit`.
      - Invokes `agent.invoke(user_input)`.
      - Catches and logs exceptions + traceback.

## Configuration/Dependencies
- **Filesystem**
  - Writes logs to: `storage/datastore/interfaces/terminal_agent/<YYYYMMDDTHHMMSS>.txt`
- **Terminal behavior**
  - Uses `termios`/`tty` raw mode for interactive placeholder input (requires a TTY).
  - Uses ANSI escape sequences for cursor/line control.
- **Third-party libraries**
  - `rich` (via `console` and `rich.markdown.Markdown`)
  - `langchain_core.messages` (`AnyMessage`, `ToolMessage`)
  - `pydash` (used to find the active agent by name)
- **Internal dependencies**
  - `naas_abi_core.apps.terminal_agent.terminal_style`: `console`, `print_image`, `print_tool_response`, `print_tool_usage`
  - `naas_abi_core.services.agent.Agent.Agent`: agent interface with:
    - `.on_tool_usage(...)`, `.on_tool_response(...)`, `.on_ai_message(...)`
    - `.invoke(text)`, `.reset()`
    - `.agents`, `.name`, `.state.current_active_agent`, `.chat_model`

## Usage
Minimal example (requires a valid `Agent` instance from your application):

```python
from naas_abi_core.apps.terminal_agent.main import run_agent
from naas_abi_core.services.agent.Agent import Agent

agent = Agent(...)  # construct according to your project
run_agent(agent)
```

Interactive commands supported:
- `/?` help
- `/reset` reset the agent session
- `/bye`, `/exit`, `exit`, `quit` end the session

## Caveats
- Interactive placeholder input relies on raw terminal mode (`termios`/`tty`) and will not work on non-TTY stdin; in that case it falls back to plain `input()`.
- Conversation logging must be initialized (via `init_conversation_file()`), which `run_agent()` does automatically; otherwise `save_to_conversation()` is a no-op.
- Image rendering is triggered by detecting space-separated “words” ending in `.png/.jpg/.jpeg/.gif`; paths with trailing punctuation may not be detected.
