# docs (naas_abi_cli.cli.docs)

## What it is
CLI tooling to detect stale/missing markdown reference docs for a Python source tree and optionally regenerate them using `DocumentationAgent`. Includes helpers for file discovery, staleness checks, OpenAI API key resolution, and parallel doc generation.

## Public API

### Data types
- `RegenerationReason = Literal["missing", "outdated"]`  
  Reason a markdown file should be regenerated.

- `@dataclass DocSyncItem`
  - `source_file: Path` — Python source file.
  - `target_file: Path` — Expected markdown output path.
  - `reason: RegenerationReason` — `"missing"` or `"outdated"`.

### Functions
- `iter_python_files(source_root: Path, include_tests: bool = False) -> list[Path]`  
  Recursively lists `.py` files under `source_root`, skipping:
  - directories: `.git`, `.venv`, `venv`, `__pycache__`, `.mypy_cache`, `.pytest_cache`, `node_modules`
  - `__init__.py`
  - test files unless `include_tests=True` (files named `test_*.py` or `*_test.py`)

- `target_markdown_path(source_file: Path, source_root: Path, output_root: Path) -> Path`  
  Maps a source file to its markdown path by preserving relative path and replacing suffix with `.md`.

- `needs_regeneration(source_file: Path, target_file: Path) -> tuple[bool, RegenerationReason | None]`  
  Returns whether regeneration is needed:
  - `(True, "missing")` if target does not exist
  - `(True, "outdated")` if target mtime < source mtime
  - `(False, None)` otherwise

- `collect_docs_to_regenerate(source_root: Path, output_root: Path, include_tests: bool = False) -> list[DocSyncItem]`  
  Builds a list of `DocSyncItem` entries for files whose docs are missing/outdated.

- `resolve_openai_api_key() -> str | None`  
  Resolves `OPENAI_API_KEY`:
  - from environment (`os.getenv`)
  - else from local `.env` file (supports `export KEY=...`, comments, and quoted values)
  - if found in `.env`, also sets `os.environ["OPENAI_API_KEY"]`

- `generate_documentation_for_items(stale_docs: list[DocSyncItem], model: str, workers: int = 10) -> int`  
  Uses `DocumentationAgent(model=...)` to `generate_and_write(source_file, target_file)` for each item.
  - Runs sequentially if effective worker count is 1
  - Otherwise runs in a `ThreadPoolExecutor`
  - Raises `ValueError` if `workers < 1`
  - Raises `RuntimeError` if any file generation fails (shows up to 10 errors)
  - Returns number of successfully generated files

### Click CLI
- `docs` — click group named `docs`.

- `docs sync` (`sync_docs(...)`) — detects stale docs and optionally generates them.
  Options:
  - `--source PATH` (default `libs/naas-abi-core/naas_abi_core`) — source root directory
  - `--output PATH` (default `docs/reference`) — docs output root directory
  - `--include-tests` — include test files in checks
  - `--fail-on-stale` — exit non-zero (raises `click.ClickException`) if stale docs exist and `--generate` is not used
  - `--generate` — regenerate docs using `DocumentationAgent` (requires `OPENAI_API_KEY`)
  - `--model TEXT` (default `gpt-5.2`) — model id passed to `DocumentationAgent`
  - `--workers INT` (default `10`, min `1`) — parallelism for generation

## Configuration/Dependencies
- Environment:
  - `OPENAI_API_KEY` required only when running `docs sync --generate`
  - alternatively, a local `.env` file with `OPENAI_API_KEY=...` (optionally `export OPENAI_API_KEY=...`)
- Python packages:
  - `click`
  - `naas_abi_cli.docs_builder.DocumentationAgent`
- Uses filesystem mtimes for staleness detection.

## Usage

### As a CLI command
```bash
# Check for missing/outdated docs (no generation)
python -m naas_abi_cli.cli docs sync --source libs/naas-abi-core/naas_abi_core --output docs/reference

# Generate stale docs (requires OPENAI_API_KEY)
export OPENAI_API_KEY="..."
python -m naas_abi_cli.cli docs sync --generate --workers 4
```

### As a Python module
```python
from pathlib import Path
from naas_abi_cli.cli.docs import collect_docs_to_regenerate, generate_documentation_for_items

stale = collect_docs_to_regenerate(
    source_root=Path("libs/naas-abi-core/naas_abi_core"),
    output_root=Path("docs/reference"),
)
if stale:
    generate_documentation_for_items(stale_docs=stale, model="gpt-5.2", workers=4)
```

## Caveats
- Staleness is based solely on file modification times; content changes without mtime updates won’t be detected.
- Generation failures across threads are aggregated and raised as a single `RuntimeError` (up to 10 error details shown).
- When `--generate` is used, missing `OPENAI_API_KEY` causes a `click.ClickException`.
