# terminal_style

## What it is
A small helper module for a SPARQL terminal UI that:
- Renders queries, results, and messages using **Rich** (tables, panels, syntax highlighting).
- Collects interactive user input with basic multiline support.
- Persists command/query history to `~/.sparql_terminal_history` on exit.

## Public API
Functions:
- `set_terminal_title()`: Sets the terminal title to **"SPARQL Terminal"** (Windows via `title`, Unix-like via escape sequence).
- `print_query_result(result)`: Pretty-prints SPARQL query results (expects an RDFLib `SPARQLResult`-like object with `.vars` and iterable rows).
- `print_query_error(error)`: Prints an error in a red Rich panel.
- `print_system_message(text)`: Prints a yellow "System" panel message.
- `print_query(query)`: Displays a SPARQL query with syntax highlighting (`sparql`, `monokai`) in a panel.
- `clear_screen()`: Clears the console (`rich.Console.clear()`).
- `print_welcome_message()`: Sets terminal title and prints usage/help text.
- `print_divider()`: Prints a dim horizontal divider across current console width.
- `preinput()`: Captures current readline buffer into a module-level `current_input`.
- `get_user_input()`: Reads interactive input:
  - Special commands: `exit`, `help`, `clear` (returned lowercase).
  - Multiline: collects lines until:
    - a line ends with `;`, or
    - an empty line is entered after content exists.
  - Strips a trailing `;` from the final query.
  - On `EOFError`/`KeyboardInterrupt`: prints a message and returns `"exit"`.

History persistence:
- `save_history()`: Writes `command_history` to `~/.sparql_terminal_history`.
- `load_history()`: Loads `command_history` from `~/.sparql_terminal_history` if present.

Module-level objects/state (used by the API):
- `console`: `rich.console.Console()` instance used for all I/O.
- `command_history`: list of past commands/queries (loaded at import time).
- `history_index`, `current_input`: globals (note: `history_index` is not used in current logic).

## Configuration/Dependencies
- Dependencies:
  - `rich` (`Console`, `Panel`, `Syntax`, `Text`, `Table`, `ROUNDED`)
  - Standard library: `os`, `platform`, `readline`, `atexit`
- Files:
  - History file path: `~/.sparql_terminal_history`
- Import-time side effects:
  - `load_history()` is called on import.
  - `save_history()` is registered via `atexit.register(...)`.

## Usage
```python
from naas_abi.apps.sparql_terminal import terminal_style as ts

ts.print_welcome_message()

while True:
    user_text = ts.get_user_input()
    if user_text == "exit":
        break
    if user_text == "clear":
        ts.clear_screen()
        continue
    if user_text == "help":
        ts.print_welcome_message()
        continue

    ts.print_query(user_text)
    # Execute query elsewhere and pass results to:
    # ts.print_query_result(result)
```

## Caveats
- `get_user_input()` relies on `rich.Console.input()` and `readline`; history navigation behavior depends on the runtime environment and terminal support.
- History saving/loading silently ignores all exceptions (failures won’t be reported).
- Multiline termination is simplistic: a trailing `;` ends input and is removed from the final query string.
