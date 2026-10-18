# `terminal_style`

## What it is
A small set of Rich-based terminal UI helpers for an agent CLI:
- Formats agent responses, system messages, code blocks, tool usage/events, and images.
- Handles terminal title setting, screen clearing, divider printing, and user input.

## Public API
Functions:

- `set_terminal_title()`
  - Sets the terminal window title to `ABI` (Windows via `title`, Unix-like via escape sequence).

- `print_agent_response(text, agent_label)`
  - Prints an agent label and a Markdown-formatted response with spacing.

- `print_system_message(text)`
  - Prints a yellow “System” panel containing `text`.

- `print_code(code, language="python")`
  - Prints a syntax-highlighted code panel (Monokai theme, line numbers).

- `dict_to_equal_string(d: dict) -> str`
  - Converts a dict to newline-separated `-key="value"` lines.

- `print_tool_usage(message)`
  - Prints tool usage / events for different payload shapes:
    - If `message.tool_calls` exists and non-empty, prints:
      - Delegation message for tool names starting with `transfer_to_...`
      - Otherwise a “Tool Used” line and formatted args (via `dict_to_equal_string`)
    - If `message` is a dict with `"content"`, prints an “Event” line.
    - If `message` has `.content`, prints an “Event” line.
    - Fallback: prints `message` as an “Event”.

- `print_tool_response(response)`
  - Prints a “Response” line with the given `response`.

- `clear_screen()`
  - Clears the console (`console.clear()`).

- `print_welcome_message(agent)`
  - Sets terminal title, otherwise intentionally does nothing (`pass`).

- `print_divider()`
  - Prints a dim horizontal divider across the current console width.

- `get_user_input(agent_label)`
  - Prompts the user with a styled `You:` input line.
  - Returns the input string; on `EOFError`/`KeyboardInterrupt`, prints a termination message and returns `"exit"`.

- `print_image(image_path: str)`
  - Prints a panel describing where an image file is saved and how to view it.
  - Attempts to open the image:
    - On Unix-like with `DISPLAY` set (and not Windows): uses PIL `Image.show()`.
    - On Windows: runs `start` to open the file.
  - Silently ignores display/open errors; on outer failure, prints a panel with the error.

## Configuration/Dependencies
- **Rich** (`rich.console.Console`, `rich.markdown.Markdown`, `rich.panel.Panel`, `rich.syntax.Syntax`, `rich.text.Text`, `rich.box.ROUNDED`)
- **Pillow** (`PIL.Image`) for optional image display.
- Standard library: `os`, `platform`, `subprocess`
- Environment:
  - `DISPLAY` is used to decide whether to attempt GUI image display on Unix-like systems.

## Usage
```python
from naas_abi_core.apps.terminal_agent import terminal_style as ts

ts.set_terminal_title()
ts.print_system_message("Starting session...")

user_text = ts.get_user_input(agent_label="ABI")
ts.print_agent_response(f"You said: {user_text}", agent_label="ABI")

ts.print_code("print('hello')", language="python")
ts.print_divider()

# If you have an image file path to show/log:
# ts.print_image("/path/to/output.png")
```

## Caveats
- `print_tool_usage()` assumes `message.tool_calls[0]` is dict-like and may raise if the structure differs.
- Image display is best-effort:
  - Requires a GUI environment (`DISPLAY`) on Unix-like systems for `Image.show()`.
  - On Windows, uses `subprocess.run(["start", "", image_path], shell=True)`.
