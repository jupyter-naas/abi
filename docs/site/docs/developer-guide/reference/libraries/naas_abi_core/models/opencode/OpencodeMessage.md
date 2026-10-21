# OpencodeMessage

## What it is
- A SQLAlchemy ORM model representing a message in an "opencode" session.
- Maps to the `opencode_messages` database table.

## Public API
- **Class: `OpencodeMessage`**
  - ORM-mapped fields:
    - `id: str` — Primary key (UUID string, auto-generated).
    - `session_id: str` — Foreign key to `opencode_sessions.id`.
    - `role: str` — Message role (stored as text).
    - `content: str | None` — Optional message content (text, nullable).
    - `parts: list[dict[str, Any]]` — JSON payload parts (defaults to empty list).
    - `created_at: datetime` — Timestamp (timezone-aware, defaults to current UTC time).

## Configuration/Dependencies
- **SQLAlchemy**: uses `mapped_column`, `Mapped`, and column types `String`, `Text`, `JSON`, `DateTime`, and `ForeignKey`.
- **Base class**: `OpencodeBase` (from `naas_abi_core.models.opencode.Base`) provides SQLAlchemy declarative base configuration.
- **Database schema**:
  - Requires a table `opencode_sessions` with primary key column `id` to satisfy `session_id` foreign key.

## Usage
```python
from sqlalchemy.orm import Session

from naas_abi_core.models.opencode.OpencodeMessage import OpencodeMessage

def create_message(db: Session, session_id: str) -> OpencodeMessage:
    msg = OpencodeMessage(
        session_id=session_id,
        role="user",
        content="Hello",
        parts=[{"type": "text", "text": "Hello"}],
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    return msg
```

## Caveats
- `parts` must be JSON-serializable (list of dicts with JSON-compatible values).
- `created_at` is set automatically to the current UTC time unless explicitly provided.
