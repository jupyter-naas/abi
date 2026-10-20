# terminal_style

## What it is
- A small set of terminal UI helpers for the **Oxigraph Admin** CLI.
- Uses the `rich` library to render styled messages, panels, tables, and prompts.

## Public API
- `set_terminal_title()`
  - Attempts to set the terminal window title to `Oxigraph Admin` using an ANSI escape sequence.
- `print_welcome_message()`
  - Clears spacing and prints a centered welcome panel (title/subtitle) and sets terminal title.
- `print_divider()`
  - Prints a dim horizontal divider sized to the current console width.
- `print_status_info(text)`
  - Prints an informational message (blue).
- `print_success_message(text)`
  - Prints a success message (green).
- `print_error_message(text)`
  - Prints an error message (red).
- `print_warning_message(text)`
  - Prints a warning message (yellow).
- `print_menu_options(options)`
  - Prints a titled list of available operations.
- `get_user_input(prompt_text="Enter your choice")`
  - Prompts the user for input via `rich.prompt.Prompt.ask`.
  - Returns `"exit"` on `KeyboardInterrupt` or `EOFError` (also prints a message on Ctrl+C).
- `clear_screen()`
  - Clears the terminal via `rich` console.
- `print_health_status(healthy: bool, message: str)`
  - Prints a green “Status” line if healthy, otherwise red.
- `print_container_info(container_data)`
  - Renders a `rich.table.Table` of container details.
  - Expects an iterable of dict-like items with keys: `Name`, `State`, `Ports`, `Created` (defaults provided).
- `print_performance_metrics(metrics)`
  - Prints a formatted list of metrics with basic key-based categorization:
    - time/latency → `ms`
    - count/total → thousands-separated
    - memory/size → printed as-is
- `print_data_stats(stats)`
  - Prints key/value stats; integers are thousands-separated.
- `confirmation_prompt(message: str, danger: bool = False) -> bool`
  - If `danger=True`: requires typing `YES` to confirm (default `NO`).
  - Else: asks to continue with choices `y/n` (default `n`).

## Configuration/Dependencies
- Dependency: `rich` (`Console`, `Panel`, `Text`, `Align`, `Prompt`, and `Table`).
- Uses a module-level `console = Console()` instance for all output.

## Usage
```python
from naas_abi.apps.oxigraph_admin import terminal_style as ui

ui.print_welcome_message()
ui.print_menu_options(["1) Health check", "2) List containers", "exit) Quit"])

choice = ui.get_user_input("Select an option")
if choice == "1":
    ui.print_health_status(True, "Oxigraph is running")
elif choice == "2":
    ui.print_container_info([
        {"Name": "oxigraph", "State": "running", "Ports": "7878/tcp", "Created": "2026-04-01"},
    ])
elif choice == "exit":
    ui.print_warning_message("Exiting...")
else:
    ui.print_error_message(f"Unknown option: {choice}")
```

## Caveats
- `set_terminal_title()` relies on ANSI escape sequences and may not work in all terminals; failures are silently ignored.
- `print_container_info()` expects `container_data` entries to be dict-like; missing keys fall back to `"Unknown"`/`"None"`.
