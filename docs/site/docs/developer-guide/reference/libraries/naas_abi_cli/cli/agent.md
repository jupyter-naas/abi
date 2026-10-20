# `agent` (CLI command group)

## What it is
- A `click` command group that exposes agent-related operations:
  - List available agents discovered by the Naas ABI engine.
  - Migrate agent “memory” (checkpoints) into the document service (schema 2).
  - Prune old stored agent memory from the document service.

## Public API
- `agent()`
  - `click` group registered as `agent`.

### Commands
- `agent list`
  - Loads `Engine()`, calls `engine.load()`, and prints a Rich table of agents (`module`, `agent.__name__`) sorted alphabetically by module then agent name.
- `agent migrate-memory`
  - Copies agent checkpoints into the document service (schema 2, incremental).
  - Supports sources:
    - `postgres` (LangGraph PostgreSQL tables) via `--source-url` / `POSTGRES_URL`.
    - `documents-v1` (legacy document schema 1 full snapshots).
  - Dry-run by default; writes only with `--apply`.
  - Outputs a JSON report to stdout.
- `agent prune-memory`
  - Deletes old checkpoints/writes/values from document-backed agent memory, keeping recent checkpoints per thread.
  - Dry-run by default; deletes only with `--apply`.
  - Outputs a JSON report to stdout.

### Internal helpers (module-private)
- `_postgres_memory(url: str) -> contextmanager[tuple[Any, Sequence[str]]]`
  - Opens a read-only PostgreSQL checkpoint source and yields `(source, thread_ids)`.
- `_documents(namespace: str) -> Any`
  - Loads the document service from engine configuration and binds it to a namespace.
- `_source(origin: str, url: str | None, namespace: str, agent_id: str) -> contextmanager`
  - Selects the checkpoint source (`postgres` or `documents-v1`) and yields `(source, thread_ids)`.

## Configuration/Dependencies
- **Core dependencies**
  - `click`
  - `rich` (`Console`, `Table`)
  - `naas_abi_core.engine.Engine.Engine` (`Engine`)
- **Engine role**
  - `use_auto_engine_role()` is invoked by `agent list`.
- **Document service**
  - Uses `EngineConfiguration.load_configuration().services.document.load()`.
  - Memory operations use `DocumentCheckpointSaver` and related migration utilities.
- **Environment**
  - `POSTGRES_URL` (optional): used by `migrate-memory` when `--from postgres` and `--source-url` is not passed.

## Usage
Register the group in your CLI:

```python
import click
from naas_abi_cli.cli.agent import agent

@click.group()
def cli():
    pass

cli.add_command(agent)

if __name__ == "__main__":
    cli()
```

Run commands:

```bash
python app.py agent list
python app.py agent migrate-memory --from postgres --source-url "$POSTGRES_URL"
python app.py agent prune-memory --keep-last 20
```

## Caveats
- The function `list()` shadows Python’s built-in `list` name within this module.
- `migrate-memory` requires a PostgreSQL URL when `--from postgres`; otherwise it raises a `click.UsageError`.
- `prune-memory` should be run while threads are idle; the docstring recommends stopping engines (API, Dagster) before migrating or pruning.
