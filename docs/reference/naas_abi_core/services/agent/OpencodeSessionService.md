# OpencodeSessionService

## What it is
- An async persistence helper for Opencode sessions, messages, and file/tool events.
- Supports two modes:
  - **Database-backed** (via `sqlalchemy.ext.asyncio.AsyncSession`)
  - **In-memory fallback** (stores sessions/messages/events in local lists/dicts)

## Public API

### Class: `OpencodeSessionService`
Creates/updates sessions and persists messages and derived file events.

#### `__init__(db_session: AsyncSession | None = None)`
- Initializes the service.
- If `db_session` is `None`, the service stores data in memory.

#### `get_or_create_session(opencode_id, agent_name, workdir, abi_thread_id, title) -> OpencodeSession`
- Looks up an `OpencodeSession` by `opencode_id` and returns it, or creates a new one.
- On existing session:
  - Updates `updated_at` to current UTC time.
  - Sets `abi_thread_id` if provided.
  - Sets `title` only if provided and session has no title yet.
- Persists via DB commit/flush when `db_session` is configured; otherwise keeps an in-memory session cache.

#### `persist_message(session, role, parts) -> OpencodeMessage`
- Creates an `OpencodeMessage` for a given session:
  - `content` is extracted from `parts` via `extract_text()`
  - `parts` is stored as-is
- Persists to DB (add + commit) or appends to an in-memory list.

#### `persist_file_events(message, parts) -> None`
- Extracts file/tool events from `parts` via `extract_file_events()`.
- Creates `OpencodeFileEvent` rows linked to:
  - `session_id = message.session_id`
  - `message_id = message.id`
- Persists to DB (add + commit) or appends to an in-memory list.

### Static helpers

#### `extract_text(parts: list[dict[str, Any]]) -> str | None`
- Collects string values from each part’s `text` or `content` key.
- Returns `None` if no text content is found; otherwise returns newline-joined text chunks.

#### `extract_file_events(parts: list[dict[str, Any]]) -> list[dict[str, Any]]`
- Parses `parts` items of `type == "tool_use"` and returns normalized event dicts.
- Recognized tool names and produced events:
  - `read` → `{"event_type": "read", "file_path": input["path"]}`
  - `write` → `{"event_type": "write", "file_path": ..., "diff": input["diff"] or input["content"]}`
  - `edit` → `{"event_type": "edit", "file_path": ..., "diff": input["diff"] or input["new_string"] or input["replace"]}`
  - `bash` → `{"event_type": "bash", "command": input["command"]}`

## Configuration/Dependencies
- Optional database integration:
  - `sqlalchemy.ext.asyncio.AsyncSession`
  - Uses `select(OpencodeSession).where(OpencodeSession.opencode_id == opencode_id)`
  - Calls `flush()` then `commit()` on each persistence operation (best-effort).
- Model dependencies (imported):
  - `OpencodeSession`, `OpencodeMessage`, `OpencodeFileEvent`
- Logging:
  - `naas_abi_core.utils.Logger.logger` used to log persistence failures.

## Usage

### In-memory (no database) example
```python
import asyncio
from naas_abi_core.services.agent.OpencodeSessionService import OpencodeSessionService

async def main():
    svc = OpencodeSessionService(db_session=None)

    session = await svc.get_or_create_session(
        opencode_id="oc_123",
        agent_name="agentA",
        workdir="/tmp/work",
        abi_thread_id=None,
        title="My session",
    )

    parts = [
        {"text": "Hello"},
        {"type": "tool_use", "name": "read", "input": {"path": "README.md"}},
    ]

    msg = await svc.persist_message(session=session, role="user", parts=parts)
    await svc.persist_file_events(message=msg, parts=parts)

asyncio.run(main())
```

## Caveats
- `_flush_best_effort()` **swallows all exceptions** and only logs an error; callers are not notified of persistence failures.
- When using the DB mode, `persist_message()` uses `session.id` and `persist_file_events()` uses `message.id`; if IDs are database-generated, availability depends on the underlying model/flush behavior.
- In-memory mode does not expose stored messages/events via a public accessor (they are kept in private attributes).
