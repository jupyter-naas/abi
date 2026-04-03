# `terminal_style`

## What it is
A small set of terminal UI helpers for the Oxigraph Admin CLI, built on top of the [`rich`](https://github.com/Textualize/rich) library. It provides consistent styled output (welcome panel, dividers, status messages, tables) and interactive prompts.

## Public API
- `console: rich.console.Console`
  - Shared `Console` instance used by all helpers.

- `set_terminal_title()`
  - Attempts to set the terminal window title to `"Oxigraph Admin"` using an ANSI escape sequence.

- `print_welcome_message()`
  - Sets the terminal title and prints a centered welcome `Panel` with title/subtitle.

- `print_divider()`
  - Prints a horizontal divider line sized to `console.width`.

- `print_status_info(text)`
  - Prints an informational line (styled, prefixed with ℹ️).

- `print_success_message(text)`
  - Prints a success line (styled, prefixed with ✅).

- `print_error_message(text)`
  - Prints an error line (styled, prefixed with ❌).

- `print_warning_message(text)`
  - Prints a warning line (styled, prefixed with ⚠️).

- `print_menu_options(options)`
  - Prints a menu header and each option from `options` (iterable of strings).

- `get_user_input(prompt_text="Enter your choice") -> str`
  - Prompts the user using `rich.prompt.Prompt.ask`.
  - Returns `"exit"` on `KeyboardInterrupt` or `EOFError` (Ctrl+C prints an exit message).

- `clear_screen()`
  - Clears the terminal via `console.clear()`.

- `print_health_status(healthy: bool, message: str)`
  - Prints a green “healthy” or red “unhealthy” status line.

- `print_container_info(container_data)`
  - Renders a `rich.table.Table` of container info.
  - Expects an iterable of dict-like objects with keys: `Name`, `State`, `Ports`, `Created` (defaults to `"Unknown"`/`"None"`).
  - Adds a colored status emoji based on `State` (`running`, `exited`, other).

- `print_performance_metrics(metrics)`
  - Prints key/value metrics with simple key-based formatting:
    - keys containing `time`/`latency` → `...ms`
    - keys containing `count`/`total` → formatted with thousands separators
    - keys containing `memory`/`size` → printed as-is
    - otherwise generic display

- `print_data_stats(stats)`
  - Prints data stats; integers are formatted with thousands separators.

- `confirmation_prompt(message: str, danger: bool = False) -> bool`
  - Asks for confirmation:
    - `danger=True`: user must type `YES` (default `NO`)
    - `danger=False`: user chooses `y`/`n` (default `n`)

## Configuration/Dependencies
- Requires `rich`:
  - `rich.console.Console`, `rich.panel.Panel`, `rich.text.Text`, `rich.align.Align`, `rich.prompt.Prompt`
  - `rich.table.Table` (imported inside `print_container_info`)
- No additional configuration; uses a module-level `Console()` instance.

## Usage
```python
from naas_abi.apps.oxigraph_admin import terminal_style as ts

ts.print_welcome_message()
ts.print_divider()

ts.print_status_info("Checking services...")
ts.print_health_status(True, "Oxigraph is responding")

ts.print_menu_options(["1) Show containers", "2) Restart service", "exit) Quit"])
choice = ts.get_user_input("Select an option")
if choice == "exit":
    raise SystemExit

containers = [
    {"Name": "oxigraph", "State": "running", "Ports": "7878/tcp", "Created": "2026-03-01"},
]
ts.print_container_info(containers)

if ts.confirmation_prompt("Restart Oxigraph?", danger=True):
    ts.print_success_message("Restart confirmed")
else:
    ts.print_warning_message("Restart cancelled")
```

## Caveats
- `set_terminal_title()` uses an ANSI escape sequence; some terminals may ignore it.
- `get_user_input()` returns the literal string `"exit"` on Ctrl+C/EOF; callers should handle this sentinel.
- Emoji characters are used in output; display depends on terminal font/encoding support.
