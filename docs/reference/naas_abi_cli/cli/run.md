# `naas_abi_cli.cli.run`

## What it is
A small `click`-based CLI command group that initializes the `naas_abi_core` `Engine` and then executes a Python script from a given file path.

## Public API
- `run()`  
  - Click command group named `run`.
- `run_script(path: str)`  
  - Click subcommand `run script PATH`.
  - Behavior:
    - Instantiates `Engine` and calls `engine.load()`.
    - Executes the script at `path` using `runpy.run_path(..., run_name="__main__")`.

## Configuration/Dependencies
- Dependencies:
  - `click`
  - `naas_abi_core.engine.Engine.Engine` (imported as `Engine`)
  - Python standard library: `runpy`
- No configuration options are defined in this module.

## Usage
Minimal CLI invocation (assuming the CLI entrypoint wires this group in):
```bash
naas-abi run script /path/to/script.py
```

If you need to invoke the command function directly (not typical for `click`):
```python
from naas_abi_cli.cli.run import run_script

run_script("/path/to/script.py")
```

## Caveats
- The script is executed with `__name__ == "__main__"` via `runpy.run_path`, so it behaves like a directly-run Python script.
- Any exceptions raised by `Engine.load()` or by the target script will propagate (no error handling in this module).
