# `terminal_style`

## What it is
A small helper module for rendering terminal UI elements for an agent CLI using the `rich` library (panels, markdown, syntax highlighting), plus basic helpers for clearing the screen, reading user input, and optionally opening generated images.

## Public API
- `set_terminal_title()`
  - Sets the terminal window title to `ABI` (Windows via `title`, Unix-like via escape sequence).
- `print_agent_response(text, agent_label)`
  - Prints an agent label and a Markdown-rendered response with spacing.
- `print_system_message(text)`
  - Prints a yellow “System” panel containing the given text.
- `print_code(code, language="python")`
  - Prints syntax-highlighted code in a red panel (line numbers enabled).
- `dict_to_equal_string(d: dict) -> str`
  - Converts a dict to lines formatted as `-key="value"` (one per line).
- `print_tool_usage(message)`
  - Prints tool usage based on `message.tool_calls[0]`:
    - If tool name starts with `transfer_to_`, prints a “Delegated to …” line.
    - Otherwise prints “Tool Used” plus formatted args (if present under `args`).
- `print_tool_response(response)`
  - Prints a “Response:” line.
- `clear_screen()`
  - Clears the terminal via `rich` console.
- `print_welcome_message(agent)`
  - Sets terminal title then does nothing else (welcome output is intentionally skipped).
- `print_divider()`
  - Prints a dim horizontal divider sized to the console width.
- `get_user_input(agent_label)`
  - Prompts the user for input (`You:`). Returns `"exit"` on `EOFError` or `KeyboardInterrupt` and prints a termination message.
- `print_image(image_path: str)`
  - Prints a panel with the saved image path and viewing instructions.
  - Attempts to open the image:
    - On Unix-like with `DISPLAY` set: uses `PIL.Image.open(...).show()`.
    - On Windows: runs `start` via `subprocess`.

## Configuration/Dependencies
- Dependencies:
  - `rich` (`Console`, `Markdown`, `Panel`, `Syntax`, `Text`, `ROUNDED`)
  - `Pillow` (`PIL.Image`) for optional image opening
- Environment/OS behavior:
  - Uses `platform.system()` to switch Windows vs Unix-like behavior.
  - Uses `DISPLAY` env var to decide whether to try opening images on Unix-like systems.

## Usage
```python
from naas_abi_core.apps.terminal_agent import terminal_style as ts

ts.set_terminal_title()
ts.print_system_message("Starting session...")
ts.print_agent_response("Hello **world**!", agent_label="ABI")
ts.print_code("print('hi')\n", language="python")
ts.print_divider()

user_text = ts.get_user_input(agent_label="ABI")
if user_text == "exit":
    ts.print_system_message("Goodbye.")
```

## Caveats
- `print_tool_usage(message)` expects `message.tool_calls` to exist and contain at least one item with a `"name"` key; missing/empty structures will raise errors.
- `print_image()` may silently fail to open/show images (exceptions are caught and ignored in the “open” step); it always prints the file path panel.
