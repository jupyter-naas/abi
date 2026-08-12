# `File` (SQLModel)

## What it is
A small `sqlmodel` table model representing an ingested file record, with a helper to create/use a local SQLite database (`files.db`) and ensure the table schema exists.

## Public API
- `class File(SQLModel, table=True)`
  - Table columns:
    - `id: int` — Primary key (auto/default `None` until persisted).
    - `name: str` — File name.
    - `hash: str` — File hash (string).
  - `@staticmethod File.engine() -> Engine`
    - Creates a SQLite engine targeting `files.db`.
    - Ensures all tables in `File.metadata` are created.
    - Returns the engine for use with `sqlmodel.Session`.

## Configuration/Dependencies
- Dependencies:
  - `sqlmodel.SQLModel`, `sqlmodel.Field`
  - `naas_abi_marketplace.domains.document.lib.sqlmodel_sqlite.create_sqlite_engine`
- Side effects:
  - Creates/uses a SQLite database file named `files.db` in the current working directory.
  - Executes `File.metadata.create_all(engine)` each time `engine()` is called.

## Usage
```python
from sqlmodel import Session
from naas_abi_marketplace.domains.document.pipelines.FilesIngestion.models import File

engine = File.engine()

with Session(engine) as session:
    f = File(name="example.pdf", hash="abc123")
    session.add(f)
    session.commit()
    session.refresh(f)
    print(f.id, f.name, f.hash)
```

## Caveats
- The database filename is hard-coded to `files.db`; its location depends on the process working directory.
- `File.engine()` will attempt to create the schema on every call (idempotent in SQLite).
