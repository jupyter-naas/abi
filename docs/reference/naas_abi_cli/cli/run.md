# `run` (CLI command group)

## What it is
- A `click` command group that provides a `run script` subcommand to execute a Python script after loading the ABI engine.
- Forwards extra CLI arguments to the target script via `sys.argv`.

## Public API
- `run()`
  - Click command group named `run`.
- `run_script(ctx: click.Context, path: str)`
  - Click subcommand: `run script <path> [args...]`
  - Calls `use_auto_engine_role()`, then loads `naas_abi_core.engine.Engine.Engine` via `Engine().load()`.
  - Executes the script at `path` using `runpy.run_path(..., run_name="__main__")`.
  - Forwards any additional CLI args to the executed script (`sys.argv = [path, *ctx.args]`).

## Configuration/Dependencies
- Dependencies:
  - `click`
  - `naas_abi_core.engine.Engine.Engine`
  - `naas_abi_cli.cli.engine_role.use_auto_engine_role`
  - Standard library: `runpy`, `sys`
- Click context settings for `run script`:
  - `ignore_unknown_options=True`
  - `allow_extra_args=True`
  - Purpose: accept arbitrary arguments and pass them through to the target script.

## Usage
Run a script and pass through arguments:
```bash
abi run script ./myscript.py --foo bar
```

Example script reading forwarded args:
```python
# myscript.py
import sys
print(sys.argv)
```

## Caveats
- Mutates `sys.argv` before executing the script (`sys.argv = [path, *ctx.args]`).
- The script is executed as `__main__` via `runpy.run_path`, as if invoked directly.
