# docs (naas_abi_cli.cli.docs)

## What it is
CLI and helper utilities to:
- Scan a Python source tree for `.py` files (optionally including tests)
- Determine which corresponding Markdown reference docs are missing or outdated
- Optionally regenerate stale docs in parallel using `DocumentationAgent`

## Public API

### Data types
- `RegenerationReason = Literal["missing", "outdated"]`  
  Reason a doc file should be regenerated.

- `@dataclass DocSyncItem`  
  Represents a doc sync action:
  - `source_file: Path` — Python source file
  - `target_file: Path` — expected/generated Markdown file
  - `reason: RegenerationReason` — `"missing"` or `"outdated"`

### File discovery and staleness
- `iter_python_files(source_root: Path, include_tests: bool = False) -> list[Path]`  
  Recursively lists Python files under `source_root`, skipping:
  - directories: `.git`, `.venv`, `venv`, `__pycache__`, `.mypy_cache`, `.pytest_cache`, `node_modules`
  - `__init__.py`
  - test files unless `include_tests=True` (`test_*.py` or `*_test.py`)

- `target_markdown_path(source_file: Path, source_root: Path, output_root: Path) -> Path`  
  Maps a source file to its expected Markdown path under `output_root`, preserving relative path and changing suffix to `.md`.

- `needs_regeneration(source_file: Path, target_file: Path) -> tuple[bool, RegenerationReason | None]`  
  Determines whether regeneration is needed:
  - `"missing"` if `target_file` does not exist
  - `"outdated"` if `target_file` mtime is older than `source_file` mtime
  - otherwise returns `(False, None)`

- `collect_docs_to_regenerate(source_root: Path, output_root: Path, include_tests: bool = False) -> list[DocSyncItem]`  
  Produces a list of `DocSyncItem` for all missing/outdated docs.

### API key resolution
- `resolve_openai_api_key() -> str | None`  
  Resolves `OPENAI_API_KEY` by:
  1. Checking environment variable `OPENAI_API_KEY`
  2. Falling back to reading `OPENAI_API_KEY` from a local `.env` file (supports `export KEY=...`, comments, and quoted values)  
  If found in `.env`, it also sets `os.environ["OPENAI_API_KEY"]`.

### Documentation generation
- `generate_documentation_for_items(stale_docs: list[DocSyncItem], model: str, workers: int = 10) -> int`  
  Generates docs for each `DocSyncItem` using `DocumentationAgent(model=model).generate_and_write(...)`.
  - Runs sequentially if effective worker count is 1; otherwise uses `ThreadPoolExecutor`.
  - Raises `ValueError` if `workers < 1`.
  - Raises `RuntimeError` if one or more files fail (includes up to 10 error lines).
  - Returns number of successfully generated files.

### CLI
- `docs()` (Click group: `docs`)  
  “Documentation tooling for ABI projects.”

- `sync_docs(...)` (Click command: `docs sync`)  
  Detects stale docs; optionally generates them.

  Options:
  - `--source` (dir, default `libs/naas-abi-core/naas_abi_core`)
  - `--output` (dir, default `docs/reference`)
  - `--include-tests`
  - `--fail-on-stale` (exit non-zero if stale docs detected and not generating)
  - `--generate` (generate/update stale docs)
  - `--model` (default `gpt-5.2`)
  - `--workers` (min 1, default 10)

## Configuration/Dependencies
- Depends on `click` for CLI.
- Depends on `naas_abi_cli.docs_builder.DocumentationAgent` for generation.
- `--generate` requires `OPENAI_API_KEY`:
  - either exported in the environment, or
  - present in a local `.env` file as `OPENAI_API_KEY=...` (optionally `export ...` and/or quoted).

## Usage

### CLI: check for stale docs
```bash
python -m naas_abi_cli.cli.docs docs sync --source libs/naas-abi-core/naas_abi_core --output docs/reference
```

### CLI: generate stale docs
```bash
export OPENAI_API_KEY="your-key"
python -m naas_abi_cli.cli.docs docs sync --generate --model gpt-5.2 --workers 10
```

### Python: list stale docs and generate
```python
from pathlib import Path
from naas_abi_cli.cli.docs import (
    collect_docs_to_regenerate,
    generate_documentation_for_items,
    resolve_openai_api_key,
)

stale = collect_docs_to_regenerate(
    source_root=Path("libs/naas-abi-core/naas_abi_core"),
    output_root=Path("docs/reference"),
)
if stale and resolve_openai_api_key():
    generate_documentation_for_items(stale_docs=stale, model="gpt-5.2", workers=4)
```

## Caveats
- Test file detection is name-based only (`test_*.py` or `*_test.py`).
- Staleness is based solely on filesystem modification times (mtime).
- On parallel generation, failures are aggregated and raised as a single `RuntimeError` (only first 10 errors included).
