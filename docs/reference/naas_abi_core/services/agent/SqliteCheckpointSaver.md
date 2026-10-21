# SqliteCheckpointSaver

## What it is
- A SQLite-backed checkpoint saver that extends `langgraph.checkpoint.memory.InMemorySaver`.
- Keeps LangGraph’s in-memory checkpoint state, but persists it to a local SQLite database after each write/delete operation.
- Thread-safe via an internal re-entrant lock (`threading.RLock`).

## Public API
### Class: `SqliteCheckpointSaver(InMemorySaver)`
- `__init__(path: str, journal_mode: str = "WAL", busy_timeout_ms: int = 5000) -> None`
  - Creates/opens a SQLite DB at `path`, initializes schema, and loads previously persisted state (if present).
- `get_tuple(config: RunnableConfig) -> CheckpointTuple | None`
  - Thread-safe wrapper around `InMemorySaver.get_tuple`.
- `list(config: RunnableConfig | None, *, filter: dict[str, Any] | None = None, before: RunnableConfig | None = None, limit: int | None = None)`
  - Thread-safe generator wrapper around `InMemorySaver.list`.
- `put(config: RunnableConfig, checkpoint: Checkpoint, metadata: CheckpointMetadata, new_versions: ChannelVersions) -> RunnableConfig`
  - Stores a checkpoint via `InMemorySaver.put` and then persists the full state to SQLite.
- `put_writes(config: RunnableConfig, writes, task_id: str, task_path: str = "") -> None`
  - Stores writes via `InMemorySaver.put_writes` and then persists the full state to SQLite.
- `delete_thread(thread_id: str) -> None`
  - Deletes all checkpoints for a thread via `InMemorySaver.delete_thread` and then persists the full state to SQLite.
- `close() -> None`
  - Closes the underlying SQLite connection.

## Configuration/Dependencies
- **Dependencies**
  - `langgraph.checkpoint.memory.InMemorySaver`
  - `sqlite3`, `pickle`, `threading`, `os`, `time`
- **SQLite behavior**
  - Creates a table `checkpoint_state` with a single row (`id = 1`) holding:
    - `storage` (pickled), `writes` (pickled), `blobs` (pickled), `updated_at` (timestamp)
  - PRAGMAs set on init:
    - `journal_mode` (default `"WAL"`)
    - `busy_timeout` (default `5000` ms)
    - `synchronous=NORMAL`
- **Filesystem**
  - Ensures the directory for `path` exists (`os.makedirs(os.path.dirname(path) or ".", exist_ok=True)`).

## Usage
```python
from naas_abi_core.services.agent.SqliteCheckpointSaver import SqliteCheckpointSaver

# Create/open a persisted checkpoint store
saver = SqliteCheckpointSaver(path="./checkpoints.sqlite")

# Use 'saver' wherever a LangGraph checkpointer/saver is expected.
# (Checkpoint creation and config structure depend on LangGraph usage.)

# Always close when done
saver.close()
```

## Caveats
- Uses `pickle` for persistence; the loaded data is assumed to come from the same local process/database (not intended for untrusted input).
- Persists the *entire* in-memory state on each `put`, `put_writes`, and `delete_thread` (may be costly for large stores).
- `close()` only closes the SQLite connection; it does not explicitly flush beyond the commits already performed during persistence.
