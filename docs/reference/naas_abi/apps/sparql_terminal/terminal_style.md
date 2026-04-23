# `terminal_style`

## What it is
Utilities for a Rich-powered SPARQL terminal UI:
- Pretty-print SPARQL queries, results, errors, and system messages
- Read user input with simple multiline support and in-memory history
- Persist command/query history to `~/.sparql_terminal_history`
- Set the terminal window title to **“SPARQL Terminal”**

## Public API
Functions:
- `set_terminal_title()`: Set terminal title to `"SPARQL Terminal"` (Windows via `title`, Unix-like via escape sequence).
- `print_query_result(result)`: Render a SPARQL result (expects an iterable with `.vars`) as a Rich table.
- `print_query_error(error)`: Render an exception/error message inside a red Rich panel.
- `print_system_message(text)`: Render a yellow “System” panel with the provided text.
- `print_query(query)`: Render a SPARQL query with syntax highlighting inside a panel.
- `clear_screen()`: Clear the terminal using Rich (`console.clear()`).
- `print_welcome_message()`: Set title and print an introductory panel with usage instructions.
- `print_divider()`: Print a dim horizontal divider sized to the console width.
- `preinput()`: Save current readline buffer into `current_input` and return it.
- `get_user_input()`: Prompt for user input:
  - Recognizes special commands: `exit`, `help`, `clear` (returns lowercase)
  - Supports multiline queries; terminates on a line ending with `;` or on an empty line after content
  - Stores unique commands/queries in an in-memory history list
  - Returns `"exit"` on `EOFError` or `KeyboardInterrupt`
- `save_history()`: Write `command_history` to `~/.sparql_terminal_history` (best-effort; errors ignored).
- `load_history()`: Load history from `~/.sparql_terminal_history` into `command_history` (best-effort; errors ignored).

Module-level behavior:
- Registers `save_history()` via `atexit.register(save_history)`.
- Calls `load_history()` at import time.

## Configuration/Dependencies
Dependencies:
- `rich` (`Console`, `Panel`, `Syntax`, `Text`, `Table`, `ROUNDED`)
- Standard library: `os`, `platform`, `readline`, `atexit`

Files:
- History file: `~/.sparql_terminal_history`

State:
- Uses module globals:
  - `command_history` (list)
  - `history_index` (int; defined but not used in current logic)
  - `current_input` (str)

## Usage
Minimal example (interactive):

```python
from naas_abi.apps.sparql_terminal.terminal_style import (
    print_welcome_message,
    get_user_input,
    print_query,
)

print_welcome_message()

while True:
    user_text = get_user_input()
    if user_text == "exit":
        break
    if user_text in ("help", "clear"):
        # caller handles these commands as desired
        print(f"Command: {user_text}")
        continue

    print_query(user_text)  # display what was entered
```

Printing results (expects an object similar to RDFLib `SPARQLResult` with `.vars` and row iteration):

```python
from naas_abi.apps.sparql_terminal.terminal_style import print_query_result

# result = graph.query("SELECT ...")  # from RDFLib (not shown)
# print_query_result(result)
```

## Caveats
- Importing the module loads history immediately and registers an `atexit` handler that writes history on process exit.
- `get_user_input()` uses `console.input()` and does not implement custom key handling; history navigation depends on the underlying readline behavior.
- Multiline termination rules:
  - A line ending with `;` ends input (the final `;` is stripped from the returned query).
  - An empty line ends input only after at least one line has been entered.
