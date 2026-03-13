# `run_migrations`

## What it is
A small async script that scans a `migrations/` directory next to the module, reads `*.sql` files in sorted order, splits them into SQL statements, and executes them using an async SQLAlchemy engine.

## Public API
- `async def run_migrations()`
  - Finds `*.sql` migration files under `Path(__file__).parent / "migrations"`.
  - Parses SQL into statements by detecting line-ending `;`.
  - Executes each statement via `await conn.execute(sqlalchemy.text(statement))`.
  - Prints progress and continues on errors; skips errors whose message contains `"already exists"` (case-insensitive).

## Configuration/Dependencies
- **Directory layout**
  - Expects a sibling directory: `migrations/` containing `*.sql` files.
- **Database**
  - Uses `app.core.database.async_engine` (must be importable and configured for your environment).
- **Libraries**
  - `sqlalchemy` (for `text()` and async execution)
  - `asyncio`, `pathlib`

## Usage
### Run as a script
```bash
python libs/naas-abi/naas_abi/apps/nexus/apps/api/run_migrations.py
```

### Call from Python (async)
```python
import asyncio
from naas_abi.apps.nexus.apps.api.run_migrations import run_migrations

asyncio.run(run_migrations())
```

## Caveats
- Statement splitting is simplistic:
  - Only treats a statement as complete when a **line ends with `;`**.
  - Multi-line statements are supported, but semicolons not at end-of-line may not split as expected.
- Error handling:
  - On execution errors, the script logs the error and continues.
  - Only errors containing `"already exists"` are explicitly treated as “skip”; other failures do not stop the run.
- Comments:
  - Lines starting with `--` are skipped.
  - Inline `-- ...` comments are stripped from a line.
