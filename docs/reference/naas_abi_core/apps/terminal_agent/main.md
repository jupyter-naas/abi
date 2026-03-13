# terminal_agent.main

## What it is
- Terminal UI runner for a `naas_abi_core.services.agent.Agent.Agent` instance.
- Provides:
  - Interactive prompt with a placeholder (TTY mode) and plain input (piped/non-TTY mode).
  - Console rendering for AI messages, tool usage, and tool responses.
  - Conversation logging to timestamped files under `storage/datastore/interfaces/terminal_agent/`.

## Public API
- `init_conversation_file() -> Path`
  - Creates a new timestamped conversation log file and writes a header.
  - Stores the path in the module-global `conversation_file`.

- `save_to_conversation(line: str) -> None`
  - Appends a single line (plus newline) to the active conversation file (if initialized).

- `get_input_with_placeholder(prompt: str = "> ", placeholder: str = "Send a message (/? for help)") -> str`
  - Reads user input.
  - If `stdin` is not a TTY, falls back to standard `input()`.
  - If `stdin` is a TTY, uses raw terminal mode to display a grey placeholder that disappears on first keystroke.

- `on_tool_response(message: AnyMessage) -> None`
  - Formats and prints tool responses via `print_tool_response(...)`.
  - If the response text contains words ending in `.png`, `.jpg`, `.jpeg`, `.gif`, attempts to render them via `print_image(path)`.

- `on_ai_message(message: Any, agent_name: str) -> None`
  - Renders AI output as Markdown via `rich`.
  - Extracts and displays `<think>...</think>` blocks as “Thoughts:” in grey, and removes them from the main displayed content.
  - Logs output (including thoughts and a fixed-width separator) to the conversation file.

- `run_agent(agent: Agent) -> None`
  - Main interactive loop:
    - Initializes conversation logging.
    - Registers agent hooks:
      - `agent.on_tool_usage(...)` → `print_tool_usage`
      - `agent.on_tool_response(...)` → `on_tool_response`
      - `agent.on_ai_message(...)` → `on_ai_message`
    - Prints/logs a greeting: `"{agent.name}: Hello, World!"`.
    - Repeatedly:
      - Prints/logs active agent + model info from `agent.state.current_active_agent` and `chat_model.model_name`/`chat_model.model`.
      - Reads user input.
      - Handles commands:
        - Exit: `exit`, `quit`, `/exit`, `/quit`, `/bye`
        - Reset: `reset`, `/reset` (calls `agent.reset()`)
        - Help: `/?` (prints available commands and agent handles)
      - Otherwise calls `agent.invoke(user_input)`.
    - On exceptions from `agent.invoke`, prints/logs error and full traceback and continues.

## Configuration/Dependencies
- Terminal/OS:
  - Uses `termios` and `tty` raw mode for interactive placeholder input (POSIX-like terminals).
  - Checks `sys.stdin.isatty()` to decide between interactive vs piped input mode.

- External libraries/services:
  - `naas_abi_core.logger` for logging conversation file location.
  - `naas_abi_core.apps.terminal_agent.terminal_style`:
    - `console` (Rich console)
    - `print_image`, `print_tool_response`, `print_tool_usage`
  - `langchain_core.messages` (`AnyMessage`, `ToolMessage`) for tool response typing.
  - `pydash` is imported inside `run_agent` to find the active agent in `agent.agents + [agent]`.
  - `rich.markdown.Markdown` is imported inside `on_ai_message`.

- Conversation logs:
  - Directory: `storage/datastore/interfaces/terminal_agent/`
  - Filename: `{YYYYMMDDTHHMMSS}.txt`
  - Uses a fixed separator width in logs: `TERMINAL_WIDTH = 77` (even though display separator uses `console.width`).

## Usage
Minimal example (requires a compatible `Agent` instance from your application):

```python
from naas_abi_core.apps.terminal_agent.main import run_agent
from your_project import build_agent  # must return an naas_abi_core Agent

agent = build_agent()
run_agent(agent)
```

Non-interactive (piped) input is supported; the prompt falls back to `input()` when `stdin` is not a TTY.

## Caveats
- Interactive placeholder input uses `termios`/`tty`; it may not work on non-POSIX environments.
- Conversation logging must be initialized via `init_conversation_file()` (called by `run_agent`) or `save_to_conversation()` will no-op.
- Image rendering is triggered by any whitespace-delimited “word” ending in a supported image extension; paths are not otherwise validated here.
- Log separators are fixed-width (`77`), while on-screen separators use dynamic `console.width`, so logs may not match the exact terminal width.
