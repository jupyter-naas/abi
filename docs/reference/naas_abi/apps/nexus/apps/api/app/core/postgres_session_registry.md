# PostgresSessionRegistry

## What it is
- A singleton registry that:
  - Stores `sqlalchemy.ext.asyncio.AsyncSession` objects by `session_id`.
  - Tracks the “current” session id using a `contextvars.ContextVar` (context-local; useful in async/concurrent code).

## Public API
### Data structures
- `SessionBinding(session_id: str, db: AsyncSession)`
  - Immutable dataclass pairing a `session_id` with an `AsyncSession`.

### Class: `PostgresSessionRegistry`
- `instance() -> PostgresSessionRegistry`
  - Returns the singleton registry.

- `bind(session_id: str, db: AsyncSession) -> None`
  - Register an `AsyncSession` under `session_id`.

- `unbind(session_id: str) -> None`
  - Remove a registered session id (no-op if missing).

- `set_current_session(session_id: str) -> contextvars.Token`
  - Set the current session id for the current context; returns a token for later reset.

- `reset_current_session(token: contextvars.Token) -> None`
  - Reset the current session id to the previous value using the token.

- `current_session_id() -> str | None`
  - Get the current session id for the current context (or `None`).

- `get(session_id: str) -> AsyncSession | None`
  - Fetch a registered session by id (or `None`).

- `current_session() -> AsyncSession | None`
  - Convenience: returns the session for the current session id (or `None`).

## Configuration/Dependencies
- Depends on:
  - `sqlalchemy.ext.asyncio.AsyncSession`
  - `contextvars.ContextVar` / `contextvars.Token`

No additional configuration is defined in this module.

## Usage
```python
from naas_abi.apps.nexus.apps.api.app.core.postgres_session_registry import PostgresSessionRegistry

registry = PostgresSessionRegistry.instance()

# db must be an AsyncSession created elsewhere
session_id = "req-123"

registry.bind(session_id, db)
token = registry.set_current_session(session_id)
try:
    current = registry.current_session()
    # use current (AsyncSession) here
finally:
    registry.reset_current_session(token)
    registry.unbind(session_id)
```

## Caveats
- This is a process-wide singleton; `_sessions` is shared across all uses in the process.
- The “current session id” is context-local (via `ContextVar`), but the session storage dict is global; callers are responsible for binding/unbinding lifecycle.
- No synchronization/locking is implemented around `_sessions`.
