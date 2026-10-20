# 20260413_add_opencode_tables

## What it is
An Alembic migration that adds three database tables for storing “opencode” session data, messages, and file-related events, plus an index on session `opencode_id`.

## Public API
- `upgrade() -> None`
  - Creates:
    - `opencode_sessions` table
    - `opencode_messages` table (FK to `opencode_sessions.id`)
    - `opencode_file_events` table (FKs to `opencode_sessions.id` and `opencode_messages.id`)
    - Index: `ix_opencode_sessions_opencode_id` on `opencode_sessions(opencode_id)`
- `downgrade() -> None`
  - Drops, in order:
    - `opencode_file_events`
    - `opencode_messages`
    - Index `ix_opencode_sessions_opencode_id`
    - `opencode_sessions`

## Configuration/Dependencies
- Alembic migration environment (imports `from alembic import op`)
- SQLAlchemy types (imports `import sqlalchemy as sa`)
- Migration identifiers:
  - `revision = "20260413_add_opencode_tables"`
  - `down_revision = None` (base migration)

### Schema created by `upgrade()`
- `opencode_sessions`
  - `id` (Text, PK, not null)
  - `opencode_id` (Text, not null) + indexed
  - `agent_name` (Text, not null)
  - `workdir` (Text, not null)
  - `abi_thread_id` (Text, nullable)
  - `title` (Text, nullable)
  - `created_at` (DateTime(timezone=True), not null)
  - `updated_at` (DateTime(timezone=True), not null)

- `opencode_messages`
  - `id` (Text, PK, not null)
  - `session_id` (Text, not null, FK → `opencode_sessions.id`)
  - `role` (Text, not null)
  - `content` (Text, nullable)
  - `parts` (JSON, not null)
  - `created_at` (DateTime(timezone=True), not null)

- `opencode_file_events`
  - `id` (Text, PK, not null)
  - `session_id` (Text, not null, FK → `opencode_sessions.id`)
  - `message_id` (Text, not null, FK → `opencode_messages.id`)
  - `event_type` (Text, not null)
  - `file_path` (Text, nullable)
  - `diff` (Text, nullable)
  - `command` (Text, nullable)
  - `created_at` (DateTime(timezone=True), not null)

## Usage
Run via Alembic (typical invocation):

```bash
alembic upgrade head
```

If you need to revert:

```bash
alembic downgrade -1
```

## Caveats
- No server defaults are defined for timestamps; application code must supply `created_at`/`updated_at` values when inserting rows.
- `down_revision = None` indicates this is a base migration; ensure it matches your project’s migration history expectations.
