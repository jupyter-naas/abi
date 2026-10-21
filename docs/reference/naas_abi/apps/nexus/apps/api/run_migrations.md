# `run_migrations`

## What it is
A small async script that runs pending SQL migrations by reading `*.sql` files from a local `migrations/` directory and executing their SQL statements against a SQLAlchemy async engine.

## Public API
- `async def run_migrations()`
  - Discovers migration files, parses SQL into statements, and executes them sequentially within a single `async_engine.begin()` transaction context.
  - Logs progress to stdout.
  - On execution errors:
    - If the error message contains `"already exists"` (case-insensitive), logs and skips.
    - Otherwise logs the error and continues with remaining statements/migrations.

## Configuration/Dependencies
- **Filesystem**
  - Expects a directory at: `Path(__file__).parent / "migrations"`
  - Runs all `*.sql` files in lexicographic order (use filename prefixes to control order).
- **Database**
  - Requires `app.core.database.async_engine` to be configured and importable.
  - Uses SQLAlchemy `text()` and `conn.execute(...)` for each statement.
- **SQL parsing rules**
  - Splits statements when a non-empty, non-comment line ends with `;`.
  - Skips full-line comments starting with `--` and empty lines.
  - Removes inline comments after `--` on a line.

## Usage
### Run as a script
```bash
python libs/naas-abi/naas_abi/apps/nexus/apps/api/run_migrations.py
```

### Call from Python
```python
import asyncio
from naas_abi.apps.nexus.apps.api.run_migrations import run_migrations

asyncio.run(run_migrations())
```

## Caveats
- Statement splitting is simplistic:
  - Semicolons must appear at the end of a line to terminate a statement.
  - Does not handle semicolons inside strings/procedural blocks or more complex SQL constructs reliably.
- Errors other than “already exists” are logged but do **not** stop execution; failures may leave migrations partially applied.
- No migration tracking table/versioning is implemented; it re-runs all `*.sql` files each time (relying on idempotency or “already exists” handling).
