# `bootstrap`

## What it is

Helpers to detect when the current working directory is inside a Naas ABI project (via `pyproject.toml`) and, if so, re-execute the `abi` CLI inside that project’s `uv` environment.

## Public API

- `find_abi_project_root(start_path: Path | None = None) -> Path | None`
  - Walks up from `start_path` (or `Path.cwd()`) looking for a `pyproject.toml` containing ABI project markers.
  - Returns the project root path if found; otherwise `None`.

- `maybe_rerun_in_project_context(argv: list[str]) -> bool`
  - If an ABI project is detected and safeguards allow it, executes:
    - `uv run --project <project_root> --active abi <argv...>`
  - Emits rerun info to **stderr** via `click`.
  - Returns:
    - `True` if it ran the command under `uv` successfully.
    - `False` if it chose not to rerun or could not (e.g., not in an ABI project, `uv` not found, running under pytest, recursion guard set).
  - Raises `SystemExit(returncode)` if the `uv run ...` command exits non-zero.

## Configuration/Dependencies

- Environment variables
  - `LOCAL_UV_RAN`: internal guard to prevent re-exec loops (set to `"true"` for subprocesses).
  - `PYTEST_CURRENT_TEST` / `PYTEST_VERSION`: if present, rerun is skipped.
- External tools
  - Requires `uv` available on `PATH` to perform rerun and to query project version.
- Python dependencies
  - `click` for colored stderr output.
  - `importlib.metadata.version` to read `naas-abi-cli` version (system and project).

## Usage

Minimal pattern for a CLI entrypoint:

```python
import sys
from naas_abi_cli.cli.bootstrap import maybe_rerun_in_project_context

def main() -> None:
    if maybe_rerun_in_project_context(sys.argv[1:]):
        return  # already executed under the project uv environment
    # Continue normal CLI execution here...

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
  - `LOCAL_UV_RAN` is already set.
  - Running under pytest (via env vars or `sys.argv[0]` name containing `pytest`).
- If `uv` is not installed, rerun returns `False` (no exception).
- If `uv run ...` returns non-zero, `SystemExit` is raised with the subprocess return code.
- ABI project detection is based on substring markers in `pyproject.toml` (case-insensitive).
