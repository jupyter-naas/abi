# `run` (CLI command group)

## What it is
- A `click` command group that provides a `run script` subcommand to execute a Python script after loading the ABI engine.
- Forwards extra CLI arguments to the target script via `sys.argv`.

## Public API
- `run()`
  - Click command group named `run`.
- `run_script(ctx: click.Context, path: str)`
  - Click subcommand: `run script <path> [args...]`
  - Loads `naas_abi_core.engine.Engine.Engine`, then executes the script at `path` as `__main__`.
  - Forwards any extra arguments to the executed script.

## Configuration/Dependencies
- Dependencies:
  - `click` (CLI framework)
  - `naas_abi_core.engine.Engine.Engine` (engine initialization via `Engine().load()`)
  - Standard library: `runpy`, `sys`
- Click settings for `run script`:
  - `ignore_unknown_options=True`
  - `allow_extra_args=True`
  - Purpose: accept and forward arbitrary arguments to the target script.

## Usage
Minimal example running a script and forwarding arguments:
```bash
abi run script ./myscript.py --foo bar
```

Inside the target script, arguments are available as usual:
```python
# myscript.py
import sys
print(sys.argv)
```

## Caveats
- The command mutates `sys.argv` before executing the script (`sys.argv = [path, *ctx.args]`).
- The script is executed via `runpy.run_path(..., run_name="__main__")`, so it runs as if invoked as the main module.
