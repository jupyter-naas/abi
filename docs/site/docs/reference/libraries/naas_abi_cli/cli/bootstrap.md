# bootstrap

## What it is

Utilities to detect when the current working directory is inside an ABI (naas-abi) project and, if so, re-execute the `abi` CLI inside that project’s `uv` environment.

## Public API

- `find_abi_project_root(start_path: Path | None = None) -> Path | None`
  - Walks up from `start_path` (or `Path.cwd()`) looking for a `pyproject.toml` that contains ABI project markers.
  - Returns the project root `Path` if found; otherwise `None`.

- `maybe_rerun_in_project_context(argv: list[str]) -> bool`
  - If an ABI project is detected and safeguards allow it, runs:
    - `uv run --project <project_root> --active abi <argv...>`
  - Prints rerun info via `click`.
  - Returns:
    - `True` if it successfully re-executed the command.
    - `False` if it chose not to (or could not) re-execute (e.g., not in an ABI project, uv missing, running under pytest).
  - Raises `SystemExit(returncode)` if the re-executed command fails.

## Configuration/Dependencies

- Environment variables:
  - `LOCAL_UV_RAN` (internal guard): set to prevent re-exec loops.
  - `PYTEST_CURRENT_TEST` / `PYTEST_VERSION`: if present, rerun is skipped.
- External tools:
  - Requires `uv` on `PATH` to re-execute in project context.
- Python packages:
  - Uses `click` for console output.
  - Uses `importlib.metadata.version` to fetch `naas-abi-cli` versions.

## Usage

Minimal pattern for a CLI entrypoint:

```python
import sys
from naas_abi_cli.cli.bootstrap import maybe_rerun_in_project_context

def main():
    if maybe_rerun_in_project_context(sys.argv[1:]):
        return  # command was re-run under uv/project
    # continue with normal CLI execution here

if __name__ == "__main__":
    main()
```

Finding an ABI project root:

```python
from naas_abi_cli.cli.bootstrap import find_abi_project_root

root = find_abi_project_root()
print(root)  # Path(...) or None
```

## Caveats

- Rerun is skipped when:
  - `LOCAL_UV_RAN` is already set (prevents recursion).
  - Running under pytest (detected via env vars or `sys.argv[0]` containing `pytest`).
- If `uv` is not installed, rerun returns `False` (no exception).
- If the `uv run ... abi ...` command exits non-zero, `SystemExit` is raised with that exit code.
