# `OpencodeSession`

## What it is
- A SQLAlchemy ORM model representing an OpenCode session record stored in the `opencode_sessions` table.
- Defines columns for session identity, agent/workdir metadata, optional thread/title fields, and timestamps.

## Public API
- `class OpencodeSession(OpencodeBase)`
  - ORM-mapped attributes (table columns):
    - `id: str` — Primary key (UUID string, auto-generated).
    - `opencode_id: str` — OpenCode identifier (indexed).
    - `agent_name: str` — Name of the agent.
    - `workdir: str` — Working directory for the session.
    - `abi_thread_id: str | None` — Optional ABI thread identifier.
    - `title: str | None` — Optional human-readable title.
    - `created_at: datetime` — Creation timestamp (UTC, default now).
    - `updated_at: datetime` — Update timestamp (UTC, default now).

## Configuration/Dependencies
- Depends on:
  - `sqlalchemy` (ORM mapping: `Mapped`, `mapped_column`, `String`, `Text`, `DateTime`)
  - `naas_abi_core.models.opencode.Base.OpencodeBase` (declarative base / shared model config)
- Table name: `opencode_sessions`
- Column notes:
  - `opencode_id` is indexed.
  - `abi_thread_id` and `title` are nullable.
  - `created_at`/`updated_at` use timezone-aware `DateTime(timezone=True)` with UTC defaults.

## Usage
```python
from sqlalchemy.orm import Session

from naas_abi_core.models.opencode.OpencodeSession import OpencodeSession

def create_session(db: Session) -> OpencodeSession:
    row = OpencodeSession(
        opencode_id="oc_123",
        agent_name="my-agent",
        workdir="/tmp/project",
        abi_thread_id=None,
        title="Example session",
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row
```

## Caveats
- `updated_at` is only assigned a default value on insert; there is no automatic “on update” behavior defined in this model.
